from __future__ import annotations

from pathlib import Path
import re

from PIL import Image, ImageDraw, ImageFont, ImageOps


WIDTH, HEIGHT = 1080, 1350
PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKGROUND = PROJECT_ROOT / "assets" / "buyer-fire-night-paper.png"
FONT = PROJECT_ROOT / "assets" / "fonts" / "Onest.ttf"
TEXT_COLOR = "#E9E6E2"
FONT_SIZE = 50
# Instagram's mobile profile grid displays a narrower 3:4 cover crop. Keeping
# the whole text block inside this inset makes the same asset safe both in the
# full 4:5 post and in the grid preview.
TEXT_LEFT = 165
TEXT_WIDTH = 750
LINE_SPACING = 24


def _font() -> ImageFont.FreeTypeFont:
    face = ImageFont.truetype(str(FONT), size=FONT_SIZE)
    face.set_variation_by_name("Regular")
    return face


def _wrap(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: int,
) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textbbox((0, 0), candidate, font=font)[2] <= max_width:
            current = candidate
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def render_slide(
    text: str,
    index: int,
    total: int,
    destination: Path,
    handle: str = "@geobuyerfire",
) -> None:
    """Render every slide with the exact same Buyer Fire visual system."""
    del index, total, handle
    clean = re.sub(r"\s+", " ", text.strip()).lower()
    if not clean:
        raise ValueError("slide text cannot be empty")

    with Image.open(BACKGROUND) as source:
        image = ImageOps.fit(source.convert("RGB"), (WIDTH, HEIGHT), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    face = _font()
    lines = _wrap(draw, clean, face, TEXT_WIDTH)
    if len(lines) > 5:
        raise ValueError("slide text exceeds the five-line house-style limit")

    boxes = [draw.textbbox((0, 0), line, font=face) for line in lines]
    line_heights = [box[3] - box[1] for box in boxes]
    block_height = sum(line_heights) + LINE_SPACING * (len(lines) - 1)
    y = (HEIGHT - block_height) // 2

    for line, line_height in zip(lines, line_heights):
        draw.text((TEXT_LEFT, y), line, font=face, fill=TEXT_COLOR)
        y += line_height + LINE_SPACING

    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "JPEG", quality=95, optimize=True, subsampling=0)


def render_carousel(post: dict, output_root: Path) -> list[Path]:
    slug = re.sub(r"[^a-z0-9-]+", "-", str(post["id"]).lower()).strip("-")
    folder = output_root / slug
    slides = list(post["slides"])
    paths = []
    for index, text in enumerate(slides, 1):
        path = folder / f"{index:02d}.jpg"
        render_slide(str(text), index, len(slides), path)
        paths.append(path)
    return paths
