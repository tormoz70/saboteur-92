#!/usr/bin/env python3
"""Render a raw ZX Spectrum .SCR (6144 or 6912 bytes) to PNG."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SPEC_PAL = [
    (0, 0, 0),
    (0, 0, 216),
    (216, 0, 0),
    (216, 0, 216),
    (0, 216, 0),
    (0, 216, 216),
    (216, 216, 0),
    (216, 216, 216),
    (0, 0, 0),
    (0, 0, 255),
    (255, 0, 0),
    (255, 0, 255),
    (0, 255, 0),
    (0, 255, 255),
    (255, 255, 0),
    (255, 255, 255),
]


def scr_to_image(data: bytes) -> Image.Image:
    if len(data) not in (6144, 6912):
        raise ValueError(f"Unexpected SCR size: {len(data)}")
    bitmap = data[:6144]
    attrs = data[6144:6912] if len(data) >= 6912 else bytes([0x47] * 768)
    img = Image.new("RGB", (256, 192))
    px = img.load()
    for y in range(192):
        for x in range(256):
            byte_x = x // 8
            bit = 7 - (x % 8)
            addr = ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | byte_x
            ink = (bitmap[addr] >> bit) & 1
            attr = attrs[(y // 8) * 32 + byte_x]
            paper = (attr >> 3) & 7
            bright = (attr >> 6) & 1
            if ink:
                idx = (attr & 7) + (8 if bright else 0)
            else:
                idx = paper + (8 if bright else 0)
            px[x, y] = SPEC_PAL[idx]
    return img


def main() -> None:
    src = ROOT / "assets" / "reference" / "original"
    out = src / "extracted"
    out.mkdir(parents=True, exist_ok=True)
    for path in sorted(src.glob("*.scr")) + sorted(src.glob("*.SCR")):
        img = scr_to_image(path.read_bytes())
        dst = out / f"{path.stem}_screen.png"
        img.save(dst)
        print(f"Wrote {dst}")


if __name__ == "__main__":
    main()
