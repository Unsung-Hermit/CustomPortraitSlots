#!/usr/bin/env python3
"""Generate a neutral, recognizable placeholder PNG (RGBA).

Drawn entirely by this script (no photos, no AI-generated or third-party images),
so template assets cooked from it carry no third-party content.
Corners are transparent so the texture has a real alpha channel.

Usage:
    python make_placeholder.py [output.png] [--label LABEL] [--size N]

Defaults: out/placeholder_demo.png, label "CPS DEMO", size 512.
Icon example:
    python make_placeholder.py assets/Icon128.png --label CPS --size 128
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
DEFAULT_OUT = ROOT / "out" / "placeholder_demo.png"
DEFAULT_LABEL = "CPS DEMO"
DEFAULT_SIZE = 512


def build(label: str, size: int) -> Image.Image:
    if size < 16:
        raise ValueError(f"size must be >= 16, got {size}")
    scale = size / DEFAULT_SIZE
    stripe = max(4, int(round(64 * scale)))
    body_radius = max(2, int(round(72 * scale)))
    frame_w = max(1, int(round(10 * scale)))
    inset = max(1, int(round(8 * scale)))
    plate_margin_x = max(4, int(round(40 * scale)))
    plate_top = max(inset + frame_w, int(round(176 * scale)))
    plate_bottom = min(size - inset - frame_w, int(round(336 * scale)))
    if plate_bottom - plate_top < max(12, size // 6):
        mid = size // 2
        half = max(size // 8, 12)
        plate_top = mid - half
        plate_bottom = mid + half
    plate_radius = max(2, int(round(24 * scale)))
    plate_outline = max(1, int(round(4 * scale)))
    font_size = max(10, int(round(68 * scale)))

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    # Bold diagonal stripes (orange / dark blue) inside a rounded square.
    body = Image.new("RGBA", (size, size), (24, 40, 96, 255))
    bdraw = ImageDraw.Draw(body)
    for i in range(-size, size * 2, stripe * 2):
        bdraw.polygon(
            [(i, 0), (i + stripe, 0), (i + stripe + size, size), (i + size, size)],
            fill=(255, 140, 0, 255),
        )

    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        (inset, inset, size - inset - 1, size - inset - 1),
        radius=body_radius,
        fill=255,
    )
    img.paste(body, (0, 0), mask)

    # White frame.
    draw.rounded_rectangle(
        (inset, inset, size - inset - 1, size - inset - 1),
        radius=body_radius,
        outline=(255, 255, 255, 255),
        width=frame_w,
    )

    # Center label on a dark plate; shrink font until it fits.
    plate = (plate_margin_x, plate_top, size - plate_margin_x, plate_bottom)
    draw.rounded_rectangle(
        plate,
        radius=plate_radius,
        fill=(0, 0, 0, 230),
        outline=(255, 255, 255, 255),
        width=plate_outline,
    )
    max_w = plate[2] - plate[0] - max(4, plate_outline * 4)
    max_h = plate[3] - plate[1] - max(4, plate_outline * 4)
    font = ImageFont.load_default(size=font_size)
    while font_size > 8:
        font = ImageFont.load_default(size=font_size)
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        if tw <= max_w and th <= max_h:
            break
        font_size -= 1
    else:
        bbox = draw.textbbox((0, 0), label, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    cx, cy = (plate[0] + plate[2]) // 2, (plate[1] + plate[3]) // 2
    draw.text(
        (cx - tw // 2 - bbox[0], cy - th // 2 - bbox[1]),
        label,
        font=font,
        fill=(255, 255, 255, 255),
    )
    return img


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a CPS placeholder PNG.")
    parser.add_argument(
        "output",
        nargs="?",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output PNG path (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--label",
        "-l",
        default=DEFAULT_LABEL,
        help=f'center label text (default: "{DEFAULT_LABEL}")',
    )
    parser.add_argument(
        "--size",
        "-s",
        type=int,
        default=DEFAULT_SIZE,
        help=f"square size in pixels (default: {DEFAULT_SIZE})",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    out = args.output
    out.parent.mkdir(parents=True, exist_ok=True)
    build(args.label, args.size).save(out)
    print(f"Wrote {out} ({args.size}x{args.size} RGBA, label={args.label!r})")


if __name__ == "__main__":
    main()
