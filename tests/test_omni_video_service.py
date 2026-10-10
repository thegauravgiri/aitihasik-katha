import pytest

from aitihasik_katha.core.settings import settings
from aitihasik_katha.services import omni_video_service


class _Interactions:
    def __init__(self, error):
        self.error = error
        self.calls = 0

    def create(self, **kwargs):
        self.calls += 1
        raise self.error


class _Client:
    def __init__(self, error):
        self.interactions = _Interactions(error)


@pytest.fixture
def fast(monkeypatch):
    monkeypatch.setattr(settings, "VIDEO_MODEL", "gemini-omni-1.1-flash")
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda seconds: None)


def test_content_block_is_raised_without_retrying(fast, monkeypatch, tmp_path):
    client = _Client(RuntimeError("Error code: 400 - {'error': {'message': 'Input blocked: Sorry, we can't create "
                                  "videos with real people's names or likenesses.', 'code': 'content_blocked'}}"))
    monkeypatch.setattr(omni_video_service, "get_genai_client", lambda: client)
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")

    with pytest.raises(omni_video_service.VideoBlockedError):
        omni_video_service.generate_scene_clip("prompt", str(frame), 6, str(tmp_path / "clip.mp4"))

    assert client.interactions.calls == 1


def test_other_failures_are_still_retried(fast, monkeypatch, tmp_path):
    client = _Client(RuntimeError("failed to generate asset, please retry"))
    monkeypatch.setattr(omni_video_service, "get_genai_client", lambda: client)
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")

    with pytest.raises(RuntimeError, match="failed to generate asset"):
        omni_video_service.generate_scene_clip("prompt", str(frame), 6, str(tmp_path / "clip.mp4"))

    assert client.interactions.calls == 4


OUTPUT_FILTER_ERROR = (
    "Error code: 400 - {'error': {'message': 'Request blocked due to safety violations (harmful content). "
    "Please modify your input and retry.', 'code': \"Unable to show the generated video. The video was filtered "
    "out because it violated Google's Generative AI Prohibited Use policy.\"}}"
)


def test_the_output_safety_filter_is_a_block_and_is_not_retried(fast, monkeypatch, tmp_path):
    client = _Client(RuntimeError(OUTPUT_FILTER_ERROR))
    monkeypatch.setattr(omni_video_service, "get_genai_client", lambda: client)
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")

    with pytest.raises(omni_video_service.VideoBlockedError):
        omni_video_service.generate_scene_clip("prompt", str(frame), 4, str(tmp_path / "clip.mp4"))

    assert client.interactions.calls == 1


def test_a_model_can_be_chosen_per_call(fast, monkeypatch, tmp_path):
    seen = []

    class _Seen:
        def __init__(self):
            self.interactions = self

        def create(self, **kwargs):
            seen.append(kwargs["model"])
            raise RuntimeError("stop here")

    monkeypatch.setattr(omni_video_service, "get_genai_client", lambda: _Seen())
    monkeypatch.setattr("aitihasik_katha.utils.retry.time.sleep", lambda seconds: None)
    frame = tmp_path / "frame.png"
    frame.write_bytes(b"png")

    with pytest.raises(RuntimeError):
        omni_video_service.generate_scene_clip("prompt", str(frame), 4, str(tmp_path / "clip.mp4"), model="gemini-omni-other")

    assert set(seen) == {"gemini-omni-other"}
