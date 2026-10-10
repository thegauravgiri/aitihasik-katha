import time
from pathlib import Path

from google.genai import errors, types

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.genai_client import get_genai_client
from ..utils.retry import retry
from .image_service import RATE_LIMIT_KEYWORDS
from .video_errors import VideoBlockedError, is_block_error


logger = get_logger(__name__)

# Clip lengths Veo 3.1 accepts.
VEO_DURATIONS = (4, 6, 8)
POLL_INTERVAL_SECONDS = 10


def veo_duration(seconds: float) -> int:
    """Shortest allowed clip that covers `seconds`; longer scenes get the max and are slowed later."""
    return next((d for d in VEO_DURATIONS if d >= seconds), VEO_DURATIONS[-1])


def _is_retryable(exc: BaseException) -> bool:
    """A request the API rejected as malformed or blocked will fail identically every time."""
    if isinstance(exc, VideoBlockedError):
        return False
    return not (isinstance(exc, errors.ClientError) and exc.code == 400 and "INVALID_ARGUMENT" in str(exc))


def _wait_for(operation, model: str):
    client = get_genai_client()
    deadline = time.monotonic() + settings.GENAI_REQUEST_TIMEOUT_SECONDS
    while not operation.done:
        if time.monotonic() > deadline:
            raise TimeoutError(
                f"{model} did not finish within {settings.GENAI_REQUEST_TIMEOUT_SECONDS}s"
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
def _generate_video(prompt: str, first_frame_png: bytes, seconds: int, output_path: str, model: str | None = None) -> None:
    settings.require("VIDEO_MODEL")
    model = model or settings.VIDEO_MODEL
    client = get_genai_client()
    operation = client.models.generate_videos(
        model=model,
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
    operation = _wait_for(operation, model)
    if operation.error:
        message = f"{model} failed: {operation.error}"
        raise (VideoBlockedError if is_block_error(Exception(message)) else RuntimeError)(message)

    videos = (operation.response and operation.response.generated_videos) or []
    if not videos:
        reasons = getattr(operation.response, "rai_media_filtered_reasons", None)
        message = f"{model} returned no video (filtered: {reasons})"
        # An empty result with filter reasons is the safety filter at work, not a glitch.
        raise (VideoBlockedError if reasons else RuntimeError)(message)

    video = videos[0].video
    client.files.download(file=video)
    video.save(output_path)


def generate_scene_clip(prompt: str, first_frame_path: str, seconds: int, output_path: str, model: str | None = None) -> str:
    """Animate a scene's opening frame into a `seconds`-long clip (one of VEO_DURATIONS)."""
    _generate_video(prompt, Path(first_frame_path).read_bytes(), seconds, output_path, model)
    logger.info("Generated %ss clip %s", seconds, output_path)
    return output_path
