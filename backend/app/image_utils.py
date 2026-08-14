from __future__ import annotations

from pathlib import Path
from PIL import Image, ImageOps

MAX_DIMENSION = 2200
JPEG_QUALITY = 90


def prepare_for_vision(path: str) -> str:
    """Normalize phone photos for vision while preserving small card text.

    Originals remain untouched. The returned file is a derived JPEG beside the
    upload, reducing latency/token cost and fixing phone EXIF rotation.
    """
    src = Path(path)
    dst = src.with_name(src.stem + "_vision.jpg")
    try:
        with Image.open(src) as im:
            im = ImageOps.exif_transpose(im).convert("RGB")
            if max(im.size) > MAX_DIMENSION:
                ratio = MAX_DIMENSION / max(im.size)
                im = im.resize((max(1, round(im.width * ratio)), max(1, round(im.height * ratio))), Image.Resampling.LANCZOS)
            im.save(dst, "JPEG", quality=JPEG_QUALITY, optimize=True)
        return str(dst)
    except Exception:
        # Vision API can still attempt the original if Pillow cannot decode it.
        return path
