from __future__ import annotations

from pathlib import Path
import re
import subprocess
import tempfile

import imageio_ffmpeg
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


def _vertical_canvas(source_asset: str) -> Image.Image:
    source = PROJECT_ROOT / source_asset
    if not source.exists():
        raise FileNotFoundError(f"source asset not found: {source_asset}")
    with Image.open(source) as image:
        return ImageOps.fit(
            image.convert("RGB"),
            (1080, 1920),
            Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )


def _draw_vertical_text(image: Image.Image, text: str, brand: bool = True) -> Image.Image:
    canvas = image.convert("RGBA")
    shade = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    shade_draw = ImageDraw.Draw(shade)
    shade_draw.rectangle((0, 0, 1080, 650), fill=(15, 12, 12, 92))
    shade_draw.rectangle((0, 1500, 1080, 1920), fill=(15, 12, 12, 38))
    canvas = Image.alpha_composite(canvas, shade)
    draw = ImageDraw.Draw(canvas)
    face = ImageFont.truetype(str(FONT), size=64)
    face.set_variation_by_name("Regular")
    lines = _wrap(draw, re.sub(r"\s+", " ", text.strip()).lower(), face, 820)
    if len(lines) > 4:
        raise ValueError("vertical creative text exceeds four lines")
    boxes = [draw.textbbox((0, 0), line, font=face) for line in lines]
    heights = [box[3] - box[1] for box in boxes]
    block_height = sum(heights) + 22 * max(0, len(lines) - 1)
    y = max(150, (610 - block_height) // 2)
    for line, height in zip(lines, heights):
        width = draw.textbbox((0, 0), line, font=face)[2]
        draw.text(((1080 - width) // 2, y), line, font=face, fill="#F7F3EE")
        y += height + 22
    if brand:
        brand_face = ImageFont.truetype(str(FONT), size=30)
        brand_face.set_variation_by_name("Regular")
        signature = "buyer fire"
        width = draw.textbbox((0, 0), signature, font=brand_face)[2]
        draw.text(((1080 - width) // 2, 1790), signature, font=brand_face, fill=(247, 243, 238, 190))
    return canvas.convert("RGB")


def render_story(post: dict, output_root: Path) -> Path:
    slug = re.sub(r"[^a-z0-9-]+", "-", str(post["id"]).lower()).strip("-")
    destination = output_root / "stories" / f"{slug}.jpg"
    image = _draw_vertical_text(_vertical_canvas(str(post["source_asset"])), str(post["text"]))
    destination.parent.mkdir(parents=True, exist_ok=True)
    image.save(destination, "JPEG", quality=94, optimize=True, subsampling=0)
    return destination


def render_reel(post: dict, output_root: Path) -> Path:
    slug = re.sub(r"[^a-z0-9-]+", "-", str(post["id"]).lower()).strip("-")
    destination = output_root / "reels" / f"{slug}.mp4"
    destination.parent.mkdir(parents=True, exist_ok=True)
    scenes = list(post["scenes"])
    fps = 30
    with tempfile.TemporaryDirectory() as temp_folder:
        temp_root = Path(temp_folder)
        inputs: list[str] = []
        filters: list[str] = []
        labels: list[str] = []
        for index, scene in enumerate(scenes):
            frame = _draw_vertical_text(
                _vertical_canvas(str(scene["source_asset"])),
                str(scene.get("text") or ""),
            )
            frame_path = temp_root / f"scene-{index:02d}.png"
            frame.save(frame_path, "PNG", optimize=True)
            duration = float(scene.get("duration") or 3.2)
            frame_count = max(1, round(duration * fps))
            inputs.extend(["-i", str(frame_path)])
            out = f"v{index}"
            fade_out = max(0.0, duration - 0.18)
            filters.append(
                f"[{index}:v]scale=1200:2134:force_original_aspect_ratio=increase,"
                f"crop=1080:1920,zoompan=z='min(zoom+0.0007,1.05)':d={frame_count}:"
                f"s=1080x1920:fps={fps},fade=t=in:st=0:d=0.18,"
                f"fade=t=out:st={fade_out:.3f}:d=0.18,setpts=PTS-STARTPTS[{out}]"
            )
            labels.append(f"[{out}]")
        filters.append(f"{''.join(labels)}concat=n={len(labels)}:v=1:a=0,format=yuv420p[v]")
        command = [
            imageio_ffmpeg.get_ffmpeg_exe(), "-y", *inputs,
            "-filter_complex", ";".join(filters),
            "-map", "[v]", "-r", str(fps), "-c:v", "libx264",
            "-profile:v", "high", "-level", "4.1", "-crf", "20",
            "-movflags", "+faststart", str(destination),
        ]
        subprocess.run(command, check=True, capture_output=True, text=True)
    return destination
