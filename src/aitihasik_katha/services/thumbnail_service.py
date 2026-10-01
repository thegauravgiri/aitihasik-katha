from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

from ..core.logging import get_logger
from ..utils.llm_json import ask_json
from ..utils.retry import retry
from .title_card import title_layer


logger = get_logger(__name__)

COVER_SIZE = (1080, 1920)
# Instagram's profile grid shows the middle 3:4 of a cover (y 240-1680 of 1920) and share
# previews crop to a square (y 420-1500), so the title and logo stay inside both.
TITLE_CENTER_Y = 1150
LOGO_PATH = Path("assets/logo/mark-gold.png")
MAX_TITLE_WORDS = 7

COVER_PROMPT = """You design the cover (thumbnail) of a vertical history video about Nepal. On a phone
the cover is a small tile in a grid of videos, so it must make a stranger stop and tap.

The narration, one numbered scene per line:
{scenes}

Return ONLY a JSON object with this shape:
{{"title": "...", "highlight": "...", "scene": 1}}

- title: 3 to 6 Nepali words that promise the single most shocking or curious thing in the video.
  Compress, do not copy the first sentence. No quotation marks, emojis or full stop.
- highlight: the one word from the title that carries the shock; it is shown in colour.
- scene: the number of the scene whose picture would make the most striking cover: a face, a dramatic
  object or a dramatic moment, not a map or an empty landscape.
"""


def _fallback(scenes: list[str]) -> dict:
    return {"title": " ".join(scenes[0].split()[:6]), "highlight": None, "scene": 0}


@retry(exceptions=(Exception,), max_attempts=3, delay_seconds=5)
def _ask_for_cover(scenes: list[str]) -> dict:
    numbered = "\n".join(f"{idx + 1}. {scene}" for idx, scene in enumerate(scenes))
    data = ask_json(COVER_PROMPT.format(scenes=numbered))
    if not isinstance(data, dict):
        raise ValueError(f"Cover plan has unexpected shape: {data!r}")
    words = str(data.get("title") or "").split()[:MAX_TITLE_WORDS]
    if not words:
        raise ValueError("Cover plan has no title")
    highlight = str(data.get("highlight") or "").strip(".,!?।:;")
    try:
        scene = int(data.get("scene", 1)) - 1
    except (TypeError, ValueError):
        scene = 0
    return {
        "title": " ".join(words),
        "highlight": highlight if highlight in words else None,
        "scene": scene if 0 <= scene < len(scenes) else 0,
    }


def plan_cover(scenes: list[str]) -> dict:
    """The cover's title, the word to colour and which scene's frame to use. A failure here
    falls back to the opening line over the first frame: a plain cover beats a failed run."""
    try:
        return _ask_for_cover(scenes)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Cover planning failed, using the opening line: %s", exc)
        return _fallback(scenes)


def _fill(image: Image.Image, size: tuple[int, int]) -> Image.Image:
    scale = max(size[0] / image.width, size[1] / image.height)
    resized = image.resize((round(image.width * scale), round(image.height * scale)), Image.LANCZOS)
    left, top = (resized.width - size[0]) // 2, (resized.height - size[1]) // 2
    return resized.crop((left, top, left + size[0], top + size[1]))


def _shade(width: int, height: int) -> Image.Image:
    """Dark where the title sits and a light vignette on top, so the text reads on any frame."""
    y = np.arange(height, dtype=np.float32)
    bottom = np.clip((y - 650) / 450, 0, 1) * 0.85 * np.clip((1750 - y) / 250 + 1, 0, 1)
    top = np.clip((400 - y) / 400, 0, 1) * 0.35
    alpha = (np.maximum(bottom, top) * 255).astype(np.uint8)
    return Image.fromarray(np.repeat(alpha[:, None], width, axis=1))


def render_cover(frame_path: str, title: str, highlight: str | None, output_path: str) -> str:
    """A 1080x1920 JPEG: the scene frame, a shade, the hook title and the channel mark."""
    width, height = COVER_SIZE
    image = _fill(Image.open(frame_path).convert("RGB"), COVER_SIZE)
    image = ImageEnhance.Color(ImageEnhance.Contrast(image).enhance(1.08)).enhance(1.1)
    image.paste(Image.new("RGB", COVER_SIZE, (6, 9, 20)), (0, 0), _shade(width, height))

    layer = title_layer(title, highlight, max_width=900, max_font_size=170)
    image.paste(layer, ((width - layer.width) // 2, TITLE_CENTER_Y - layer.height // 2), layer)

    if LOGO_PATH.exists():
        logo = Image.open(LOGO_PATH).convert("RGBA")
        logo = logo.resize((150, round(150 * logo.height / logo.width)), Image.LANCZOS)
        image.paste(logo, ((width - logo.width) // 2, 1500), logo)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, "JPEG", quality=92)
    return output_path
