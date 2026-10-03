import pytest

from aitihasik_katha.services import video_generation_service


@pytest.mark.parametrize(
    "model, backend",
    [("veo-3.1-lite-generate-preview", "veo"), ("veo-3.1-fast-generate-preview", "veo"),
     ("gemini-omni-1.1-flash", "omni"), ("gemini-omni-flash-preview", "omni")],
)
def test_backend_is_chosen_from_the_model_name(monkeypatch, model, backend):
    used = []
    monkeypatch.setattr(video_generation_service.settings, "VIDEO_MODEL", model)
    monkeypatch.setattr(video_generation_service.veo_video_service, "generate_scene_clip",
                        lambda *a: used.append("veo") or "out.mp4")
    monkeypatch.setattr(video_generation_service.omni_video_service, "generate_scene_clip",
                        lambda *a: used.append("omni") or "out.mp4")

    video_generation_service.generate_scene_clip("prompt", "frame.png", 4, "out.mp4")

    assert used == [backend]


def test_unknown_model_is_rejected(monkeypatch):
    monkeypatch.setattr(video_generation_service.settings, "VIDEO_MODEL", "sora-2")

    with pytest.raises(ValueError, match="Unsupported VIDEO_MODEL"):
        video_generation_service.generate_scene_clip("prompt", "frame.png", 4, "out.mp4")


def _ladder(monkeypatch, behaviours, primary="gemini-omni-1.1-flash", fallback="veo-3.1-lite-generate-preview"):
    """Fake backends: `behaviours` maps (backend, attempt number) to an exception or None for success."""
    log = []
    monkeypatch.setattr(video_generation_service.settings, "VIDEO_MODEL", primary)
    monkeypatch.setattr(video_generation_service.settings, "VIDEO_FALLBACK_MODEL", fallback)

    def _backend(name):
        def _run(prompt, frame, seconds, output, model=None):
            log.append((name, model, prompt))
            outcome = behaviours.pop(0)
            if outcome:
                raise outcome
            return output
        return _run

    monkeypatch.setattr(video_generation_service.omni_video_service, "generate_scene_clip", _backend("omni"))
    monkeypatch.setattr(video_generation_service.veo_video_service, "generate_scene_clip", _backend("veo"))
    return log


Blocked = video_generation_service.VideoBlockedError


def test_a_scene_that_is_not_blocked_costs_one_call(monkeypatch):
    log = _ladder(monkeypatch, [None])

    video_generation_service.generate_scene_clip("scene prompt", "f.png", 4, "out.mp4")

    assert [(name, prompt) for name, _, prompt in log] == [("omni", "scene prompt")]


def test_a_blocked_scene_is_retried_once_with_a_neutral_prompt(monkeypatch):
    log = _ladder(monkeypatch, [Blocked("safety"), None])

    video_generation_service.generate_scene_clip("a priest sacrifices", "f.png", 4, "out.mp4")

    assert [name for name, _, _ in log] == ["omni", "omni"]
    assert log[1][2] == video_generation_service.neutral_prompt(4)
    assert "priest" not in log[1][2] and "sacrifice" not in log[1][2]


def test_then_the_fallback_model_is_tried_with_the_neutral_prompt(monkeypatch):
    log = _ladder(monkeypatch, [Blocked("a"), Blocked("b"), None])

    video_generation_service.generate_scene_clip("p", "f.png", 6, "out.mp4")

    assert [(name, model) for name, model, _ in log] == [
        ("omni", None), ("omni", None), ("veo", "veo-3.1-lite-generate-preview"),
    ]


def test_when_every_option_is_blocked_the_caller_is_told_so_it_can_use_the_still(monkeypatch):
    _ladder(monkeypatch, [Blocked("a"), Blocked("b"), Blocked("c")])

    with pytest.raises(Blocked, match="every video option was blocked"):
        video_generation_service.generate_scene_clip("p", "f.png", 4, "out.mp4")


def test_trouble_with_the_fallback_model_never_fails_the_run(monkeypatch):
    _ladder(monkeypatch, [Blocked("a"), Blocked("b"), RuntimeError("quota exhausted")])

    with pytest.raises(Blocked, match="quota exhausted"):
        video_generation_service.generate_scene_clip("p", "f.png", 4, "out.mp4")


def test_an_ordinary_failure_of_the_main_model_still_fails_so_the_run_can_be_resumed(monkeypatch):
    log = _ladder(monkeypatch, [RuntimeError("video model unavailable")])

    with pytest.raises(RuntimeError, match="video model unavailable"):
        video_generation_service.generate_scene_clip("p", "f.png", 4, "out.mp4")

    assert len(log) == 1


def test_without_a_fallback_model_only_the_neutral_prompt_is_tried(monkeypatch):
    log = _ladder(monkeypatch, [Blocked("a"), Blocked("b")], fallback="")

    with pytest.raises(Blocked):
        video_generation_service.generate_scene_clip("p", "f.png", 4, "out.mp4")

    assert len(log) == 2


def test_the_block_wording_seen_in_real_runs_is_recognised():
    from aitihasik_katha.services.video_errors import is_block_error

    for message in (
        "Input blocked: Sorry, we can't create videos with real people's names or likenesses.",
        "Request blocked due to safety violations (harmful content). Please modify your input and retry.",
        "The video was filtered out because it violated Google's Generative AI Prohibited Use policy.",
        "Input blocked: The prompt could not be processed.",
    ):
        assert is_block_error(Exception(message)), message
    assert not is_block_error(Exception("failed to generate asset, please retry"))
    assert not is_block_error(Exception("429 Too Many Requests"))
