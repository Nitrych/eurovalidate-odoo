"""One-off: build icon.png (128×128) and banner.png (1200×400) from the repo logo.

Run from the repo root: ``python integrations/odoo/eurovalidate_vat/static/description/make_images.py``
Requires Pillow. The source logo (``logo_new.png``) is not tracked in git; pass
another path as the first argument if needed.
"""

import sys
from pathlib import Path

from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
src = Path(sys.argv[1]) if len(sys.argv) > 1 else HERE.parents[4] / "logo_new.png"

logo = Image.open(src).convert("RGBA")

icon = logo.copy()
icon.thumbnail((128, 128))
canvas = Image.new("RGBA", (128, 128), (0, 0, 0, 0))
canvas.paste(icon, ((128 - icon.width) // 2, (128 - icon.height) // 2), icon)
canvas.save(HERE / "icon.png")

banner = Image.new("RGB", (1200, 400), (10, 10, 11))
draw = ImageDraw.Draw(banner)
draw.rectangle([0, 384, 1200, 400], fill=(109, 92, 255))
draw.text((60, 140), "EuroValidate for Odoo", fill=(250, 250, 250))
draw.text((60, 190), "VAT validation + name/address autofill that keeps working when VIES is down", fill=(170, 170, 180))
big = logo.copy()
big.thumbnail((240, 240))
banner.paste(big, (900, 80), big)
banner.save(HERE / "banner.png")
print("wrote", HERE / "icon.png", HERE / "banner.png")
