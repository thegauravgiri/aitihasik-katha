import time
from pathlib import Path

from google.genai import errors, types

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.genai_client import get_genai_client
from ..utils.retry import retry
from .image_service import RATE_LIMIT_KEYWORDS


logger = get_logger(__name__)

# Clip lengths Veo 3.1 accepts.
VEO_DURATIONS = (4, 6, 8)
POLL_INTERVAL_SECONDS = 10


def veo_duration(seconds: float) -> int:
    """Shortest allowed clip that covers `seconds`; longer scenes get the max and are slowed later."""
    return next((d for d in VEO_DURATIONS if d >= seconds), VEO_DURATIONS[-1])


def _is_retryable(exc: BaseException) -> bool:
    """A request the API rejected as malformed will fail identically every time."""
    return not (isinstance(exc, errors.ClientError) and exc.code == 400 and "INVALID_ARGUMENT" in str(exc))


def _wait_for(operation):
    client = get_genai_client()
    deadline = time.monotonic() + settings.GENAI_REQUEST_TIMEOUT_SECONDS
    while not operation.done:
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"{settings.VIDEO_MODEL} did not finish within {settings.GENAI_REQUEST_TIMEOUT_SECONDS}s"
            )
        time.sleep(POLL_INTERVAL_SECONDS)
        operation = client.operations.get(operation)
    return operation


@retry(
    exceptions=(Exception,),
    max_attempts=4,
    delay_seconds=15,
    backoff_keywords=RATE_LIMIT_KEYWORDS,
    backoff_delay_seconds=90,
    should_retry=_is_retryable,
)
def _generate_video(prompt: str, first_frame_png: bytes, seconds: int, output_path: str) -> None:
    settings.require("VIDEO_MODEL")
    client = get_genai_client()
    operation = client.models.generate_videos(
        model=settings.VIDEO_MODEL,
        source=types.GenerateVideosSource(
            prompt=prompt,
            image=types.Image(image_bytes=first_frame_png, mime_type="image/png"),
        ),
        config=types.GenerateVideosConfig(
            aspect_ratio="9:16",
            duration_seconds=seconds,
            resolution="720p",
            number_of_videos=1,
        ),
    )
    operation = _wait_for(operation)
    if operation.error:
        raise RuntimeError(f"{settings.VIDEO_MODEL} failed: {operation.error}")

    videos = (operation.response and operation.response.generated_videos) or []
    if not videos:
        reasons = getattr(operation.response, "rai_media_filtered_reasons", None)
        raise RuntimeError(f"{settings.VIDEO_MODEL} returned no video (filtered: {reasons})")

    video = videos[0].video
    client.files.download(file=video)
    video.save(output_path)


def generate_scene_clip(prompt: str, first_frame_path: str, seconds: int, output_path: str) -> str:
    """Animate a scene's opening frame into a `seconds`-long clip (one of VEO_DURATIONS)."""
    _generate_video(prompt, Path(first_frame_path).read_bytes(), seconds, output_path)
    logger.info("Generated %ss clip %s", seconds, output_path)
    return output_path
