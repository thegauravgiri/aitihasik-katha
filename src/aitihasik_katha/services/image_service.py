import io
from pathlib import Path

from google.genai import types
from PIL import Image

from ..core.logging import get_logger
from ..core.settings import settings
from ..utils.genai_client import get_genai_client
from ..utils.retry import retry


logger = get_logger(__name__)

# Errors worth a long wait before retrying: quota and rate limits, and the API being briefly overloaded.
RATE_LIMIT_KEYWORDS = (
    "429", "too many requests", "rate limit", "quota", "resource_exhausted",
    "503", "unavailable", "high demand", "overloaded",
)


@retry(
    exceptions=(Exception,),
    max_attempts=4,
    delay_seconds=10,
    backoff_keywords=RATE_LIMIT_KEYWORDS,
    backoff_delay_seconds=90,
)
def generate_image(prompt: str, reference_pngs: list[bytes] = ()) -> bytes:
    """A 9:16 image from IMAGE_MODEL, optionally guided by reference images."""
    settings.require("IMAGE_MODEL")
    contents = [types.Part.from_bytes(data=png, mime_type="image/png") for png in reference_pngs]
    client = get_genai_client()

    models_to_try = [settings.IMAGE_MODEL]
    if "gemini-2.5-flash-image" not in models_to_try:
        models_to_try.append("gemini-2.5-flash-image")

    last_exc = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[*contents, prompt],
                config=types.GenerateContentConfig(
                    response_modalities=["IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio="9:16", image_size=settings.IMAGE_SIZE),
                ),
            )
            candidate = response.candidates[0] if response.candidates else None
            parts = (candidate.content.parts if candidate and candidate.content else None) or []
            for part in parts:
                if part.inline_data and part.inline_data.data:
                    return part.inline_data.data
            reason = getattr(candidate, "finish_reason", None) if candidate else "no candidates"
            logger.warning("%s returned no image data (reason: %s)", model_name, reason)
        except Exception as exc:
            if "RESOURCE_EXHAUSTED" in str(exc) or "429" in str(exc):
                logger.warning("Image model %s hit resource limit (%s), trying fallback model", model_name, exc)
                last_exc = exc
                continue
            raise

    if last_exc:
        raise last_exc
    raise RuntimeError(f"All configured image models returned no image")


def save_png(image_bytes: bytes, path: str) -> bytes:
    """Normalise any downloaded/generated image to RGB PNG."""
    buffer = io.BytesIO()
    Image.open(io.BytesIO(image_bytes)).convert("RGB").save(buffer, format="PNG")
    png = buffer.getvalue()
    Path(path).write_bytes(png)
    return png


def generate_scene_frame(prompt: str, reference_paths: list[str], output_path: str) -> str:
    """The opening frame of a scene, drawn from the characters' reference images so
    they look the same in every scene; the video model then animates this frame."""
    references = [Path(path).read_bytes() for path in reference_paths]
    save_png(generate_image(prompt, references), output_path)
    logger.info("Generated scene frame %s (%d reference image(s))", output_path, len(references))
    return output_path
