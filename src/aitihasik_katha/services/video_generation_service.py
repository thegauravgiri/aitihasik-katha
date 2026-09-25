"""Picks the video backend from VIDEO_MODEL, so switching models is a config change.

Both backends animate a scene's opening frame; character consistency comes from that
frame, which is drawn from the characters' reference images.
"""
from ..core.settings import settings
from . import omni_video_service, veo_video_service


def clip_duration(seconds: float) -> int:
    """Clip length to request for a scene of `seconds`. Both backends use Veo's 4/6/8s steps."""
    return veo_video_service.veo_duration(seconds)


def generate_scene_clip(prompt: str, first_frame_path: str, seconds: int, output_path: str) -> str:
    model = settings.VIDEO_MODEL
    if model.startswith("veo"):
        return veo_video_service.generate_scene_clip(prompt, first_frame_path, seconds, output_path)
    if model.startswith("gemini-omni"):
        return omni_video_service.generate_scene_clip(prompt, first_frame_path, seconds, output_path)
    raise ValueError(f"Unsupported VIDEO_MODEL {model!r}: use a veo-* or gemini-omni-* model")
