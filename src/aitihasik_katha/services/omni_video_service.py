import base64
from pathlib import Path

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.genai_client import get_genai_client
from ..utils.retry import retry
from .image_service import RATE_LIMIT_KEYWORDS


logger = get_logger(__name__)


# The model intermittently returns 400s like "failed to generate asset, please retry",
# so every failure is treated as retryable. Rate limits get a much longer wait.
@retry(
    exceptions=(Exception,),
    max_attempts=4,
    delay_seconds=15,
    backoff_keywords=RATE_LIMIT_KEYWORDS,
    backoff_delay_seconds=90,
)
def _generate_video(prompt: str, first_frame_png: bytes) -> bytes:
    settings.require("VIDEO_MODEL")
    interaction = get_genai_client().interactions.create(
        model=settings.VIDEO_MODEL,
        input=[
            {"type": "text", "text": prompt},
            {"type": "image", "data": base64.b64encode(first_frame_png).decode(), "mime_type": "image/png"},
        ],
        response_modalities=["video"],
        generation_config={"video_config": {"task": "image_to_video"}},
    )
    video = interaction.output_video
    if video is None or not video.data:
        raise RuntimeError(f"{settings.VIDEO_MODEL} returned no video (status={interaction.status})")
    return base64.b64decode(video.data)


def generate_scene_clip(prompt: str, first_frame_path: str, seconds: int, output_path: str) -> str:
    """Animate a scene's opening frame. The clip length is requested in `prompt`;
    the omni model has no duration setting, so the caller fits the result afterwards."""
    Path(output_path).write_bytes(_generate_video(prompt, Path(first_frame_path).read_bytes()))
    logger.info("Generated ~%ss omni clip %s", seconds, output_path)
    return output_path
