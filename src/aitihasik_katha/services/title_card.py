"""Big bold hook titles drawn with PIL, shared by the cover image and the on-video hook title."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT_PATH = Path("data/fonts/NotoSerifDevanagari-ExtraBold.ttf")
WHITE, ACCENT, OUTLINE = "#FFFFFF", "#F2B632", "#0B1020"
MAX_LINES = 3


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        return ImageFont.load_default(size)


def _wrap(words: list[str], font, max_width: int, space: float) -> list[list[str]]:
    lines: list[list[str]] = [[]]
    width = 0.0
    for word in words:
        word_width = font.getlength(word)
        if lines[-1] and width + space + word_width > max_width:
            lines.append([])
            width = 0.0
        width += (space if lines[-1] else 0) + word_width
        lines[-1].append(word)
    return lines


def title_layer(title: str, highlight: str | None, max_width: int, max_font_size: int) -> Image.Image:
    """The title as a transparent RGBA image: white words with a dark outline, the highlight
    word in the accent colour, wrapped to at most three centred lines no wider than `max_width`.
    The font shrinks until it fits."""
    words = title.split()
    font_size = max_font_size
    while True:
        font = _font(font_size)
        space = font.getlength(" ")
        lines = _wrap(words, font, max_width, space)
        fits = len(lines) <= MAX_LINES and all(font.getlength(w) <= max_width for w in words)
        if fits or font_size <= 24:
            break
        font_size = int(font_size * 0.92)

    stroke = max(4, font_size // 12)
    line_height = int(font_size * 1.28)
    pad = stroke * 2
    layer = Image.new("RGBA", (max_width + 2 * pad, line_height * len(lines) + 2 * pad), (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    for row, line in enumerate(lines):
        line_width = sum(font.getlength(w) for w in line) + space * (len(line) - 1)
        x = pad + (max_width - line_width) / 2
        y = pad + row * line_height
        for word in line:
            colour = ACCENT if highlight and word.strip(".,!?।:;") == highlight else WHITE
            draw.text((x, y), word, font=font, fill=colour, stroke_width=stroke, stroke_fill=OUTLINE)
            x += font.getlength(word) + space
    return layer
