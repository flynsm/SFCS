"""Create small JPEG previews for the home page cards.

Usage:  python3 tools/make_thumbs.py            (needs: pip install pillow)
Makes <name>-thumb.jpg next to every graphic in assets/graphics/ that lacks one.
Optional: without thumbnails the home page falls back to the full-size image.
"""
from pathlib import Path
from PIL import Image

WIDTH = 800
for png in Path(__file__).resolve().parent.parent.glob("assets/graphics/*/week-*/*.png"):
    thumb = png.with_name(png.stem + "-thumb.jpg")
    if thumb.exists():
        continue
    im = Image.open(png).convert("RGB")
    im = im.resize((WIDTH, round(im.height * WIDTH / im.width)), Image.LANCZOS)
    im.save(thumb, quality=82)
    print("made", thumb)
