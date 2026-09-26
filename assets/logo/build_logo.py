"""Regenerates every logo file in this folder: python build_logo.py (needs rsvg-convert for PNGs)."""
import subprocess

from mark_geometry import mark_shapes

BRICK, GOLD, CREAM, INK = "#7F2A1D", "#B8913F", "#F4EDE0", "#1F1A17"
LATIN = "Optima, 'Candara', 'Segoe UI', sans-serif"
DEVANAGARI = "'ITF Devanagari', 'Devanagari Sangam MN', 'Noto Sans Devanagari', sans-serif"
SHAPES = mark_shapes()


def mark(fill, dx=0, dy=0, scale=1.0):
    paths = "".join(f'<path d="{d}" fill="{fill}"/>' for d in SHAPES)
    return f'<g transform="translate({dx} {dy}) scale({scale})">{paths}</g>'


def write(name, viewbox, body, title="Aitihasik Katha"):
    with open(f"{name}.svg", "w") as f:
        f.write(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}"><title>{title}</title>{body}</svg>\n')


def build():
    # Mark alone, in each approved colourway (transparent background).
    for name, fill in {"mark": BRICK, "mark-black": "#000000", "mark-cream": CREAM, "mark-gold": GOLD}.items():
        write(name, "0 0 240 240", mark(fill, dy=6), "Aitihasik Katha mark")

    # Seal: mark reversed out of a brick disc - profile picture / stamp.
    write("seal", "0 0 240 240", f'<circle cx="120" cy="120" r="120" fill="{BRICK}"/>' + mark(CREAM, dx=18, dy=24, scale=0.85))
    write("avatar", "0 0 240 240", f'<rect width="240" height="240" fill="{BRICK}"/>' + mark(CREAM, dx=24, dy=28, scale=0.8))

    wordmark_stacked = (
        f'<text x="240" y="254" text-anchor="middle" font-family="{LATIN}" font-size="34" letter-spacing="9" fill="{INK}">AITIHASIK KATHA</text>'
        f'<line x1="212" y1="276" x2="268" y2="276" stroke="{BRICK}" stroke-width="1.6"/>'
        f'<text x="240" y="308" text-anchor="middle" font-family="{DEVANAGARI}" font-size="23" fill="{BRICK}">ऐतिहासिक कथा</text>'
    )
    write("logo-stacked", "0 0 480 336", mark(BRICK, dx=120, dy=6) + wordmark_stacked)

    wordmark_horizontal = (
        f'<text x="236" y="122" font-family="{LATIN}" font-size="46" letter-spacing="9" fill="{INK}">AITIHASIK KATHA</text>'
        f'<line x1="238" y1="146" x2="286" y2="146" stroke="{BRICK}" stroke-width="1.8"/>'
        f'<text x="300" y="156" font-family="{DEVANAGARI}" font-size="27" fill="{BRICK}">ऐतिहासिक कथा</text>'
    )
    write("logo-horizontal", "0 0 820 240", mark(BRICK, dx=0, dy=6) + wordmark_horizontal)
    write("logo-horizontal-reversed", "0 0 820 240",
          f'<rect width="820" height="240" fill="{INK}"/>' + mark(GOLD, dy=6)
          + wordmark_horizontal.replace(INK, CREAM).replace(BRICK, GOLD))

    renders = {"mark": 1024, "mark-black": 1024, "mark-cream": 1024, "mark-gold": 1024, "seal": 1080,
               "logo-stacked": 1440, "logo-horizontal": 2050, "logo-horizontal-reversed": 2050}
    for name, width in renders.items():
        subprocess.run(["rsvg-convert", "-w", str(width), f"{name}.svg", "-o", f"{name}.png"], check=True)
    subprocess.run(["rsvg-convert", "-w", "1080", "-h", "1080", "avatar.svg", "-o", "avatar-1080.png"], check=True)
    subprocess.run(["rsvg-convert", "-w", "32", "mark.svg", "-o", "favicon-32.png"], check=True)


if __name__ == "__main__":
    build()
