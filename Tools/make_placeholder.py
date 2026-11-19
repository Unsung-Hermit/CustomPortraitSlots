#!/usr/bin/env python3
"""Generate a neutral, recognizable placeholder portrait (512x512 RGBA PNG).

Drawn entirely by this script (no photos, no AI-generated or third-party images),
so template assets cooked from it carry no third-party content.
Corners are transparent so the texture has a real alpha channel.

Usage:
    python make_placeholder.py [output.png] [label]

Defaults: out/placeholder_demo.png, label "CPS DEMO".
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SIZE = 512
ROOT = Path(__file__).resolve().parent.parent


def build(label: str) -> Image.Image:
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Bold diagonal stripes (orange / dark blue) inside a rounded square.
    body = Image.new("RGBA", (SIZE, SIZE), (24, 40, 96, 255))
    bdraw = ImageDraw.Draw(body)
    stripe = 64
    for i in range(-SIZE, SIZE * 2, stripe * 2):
        bdraw.polygon(
            [(i, 0), (i + stripe, 0), (i + stripe + SIZE, SIZE), (i + SIZE, SIZE)],
            fill=(255, 140, 0, 255),
        )

    mask = Image.new("L", (SIZE, SIZE), 0)
    ImageDraw.Draw(mask).rounded_rectangle((8, 8, SIZE - 9, SIZE - 9), radius=72, fill=255)
    img.paste(body, (0, 0), mask)

    # White frame.
    draw.rounded_rectangle((8, 8, SIZE - 9, SIZE - 9), radius=72, outline=(255, 255, 255, 255), width=10)

    # Center label on a dark plate.
    font = ImageFont.load_default(size=68)
    plate = (40, 176, SIZE - 40, 336)
    draw.rounded_rectangle(plate, radius=24, fill=(0, 0, 0, 230), outline=(255, 255, 255, 255), width=4)
    bbox = draw.textbbox((0, 0), label, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = (plate[0] + plate[2]) // 2, (plate[1] + plate[3]) // 2
    draw.text((cx - tw // 2 - bbox[0], cy - th // 2 - bbox[1]), label, font=font, fill=(255, 255, 255, 255))
    return img


def main() -> None:
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "out" / "placeholder_demo.png"
    label = sys.argv[2] if len(sys.argv) > 2 else "CPS DEMO"
    out.parent.mkdir(parents=True, exist_ok=True)
    build(label).save(out)
    print(f"Wrote {out} ({SIZE}x{SIZE} RGBA)")


if __name__ == "__main__":
    main()
