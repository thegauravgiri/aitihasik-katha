"""Picks the video backend from the model name, so switching models is a config change.

Both backends animate a scene's opening frame; character consistency comes from that
frame, which is drawn from the characters' reference images.

When a model refuses a scene or filters the clip it made, the scene is not lost: it is tried
again with a neutral prompt, then with the fallback model, and only if every option is blocked
does the caller fall back to a camera move over the still frame.
"""
from ..core.logging import get_logger
from ..core.settings import settings
from . import omni_video_service, veo_video_service
from .video_errors import VideoBlockedError

__all__ = ["VideoBlockedError", "clip_duration", "generate_scene_clip", "neutral_prompt"]

logger = get_logger(__name__)


def clip_duration(seconds: float) -> int:
    """Clip length to request for a scene of `seconds`. Both backends use Veo's 4/6/8s steps."""
    return veo_video_service.veo_duration(seconds)


def neutral_prompt(seconds: int) -> str:
    """A prompt with nothing in it a safety filter could object to: the frame itself carries the scene,
    so this only asks for a slow camera move."""
    return (
        f"Animate this image into a {seconds}-second vertical 9:16 cinematic shot with a slow, steady camera "
        "push-in and subtle, natural movement. Keep everything exactly as it appears in the image. "
        "No text, no captions, no dialogue, no music."
    )


def _backend(model: str):
    if model.startswith("veo"):
        return veo_video_service.generate_scene_clip
    if model.startswith("gemini-omni"):
        return omni_video_service.generate_scene_clip
    raise ValueError(f"Unsupported VIDEO_MODEL {model!r}: use a veo-* or gemini-omni-* model")


def generate_scene_clip(prompt: str, first_frame_path: str, seconds: int, output_path: str) -> str:
    primary = settings.VIDEO_MODEL
    _backend(primary)  # an unsupported model is a configuration error, not something to fall back from
    neutral = neutral_prompt(seconds)
    attempts = [(primary, prompt)]
    if neutral != prompt:
        attempts.append((primary, neutral))
    fallback = settings.VIDEO_FALLBACK_MODEL
    if fallback and fallback != primary:
        attempts.append((fallback, neutral))

    blocked: Exception | None = None
    for model, text in attempts:
        try:
            if model == primary:
                return _backend(model)(text, first_frame_path, seconds, output_path)
            return _backend(model)(text, first_frame_path, seconds, output_path, model=model)
        except VideoBlockedError as exc:
            blocked = exc
            logger.warning("%s blocked this scene (%s); trying the next option", model, str(exc)[:120])
        except Exception as exc:  # noqa: BLE001
            if model == primary:
                raise
            # The fallback model is a safety net: its own trouble (quota, outage) must not fail the run.
            blocked = VideoBlockedError(f"fallback model {model} failed: {exc}")
            logger.warning("Fallback model %s failed: %s", model, str(exc)[:120])
    raise VideoBlockedError(f"every video option was blocked or failed: {blocked}")
