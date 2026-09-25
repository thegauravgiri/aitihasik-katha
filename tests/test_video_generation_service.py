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
