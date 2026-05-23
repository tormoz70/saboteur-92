#!/usr/bin/env python3
"""Hunt interleaved mask+bitmap sprite rows in Spectrum RAM."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from extract_from_z80 import SNAP, load_z80

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "reference" / "original" / "extracted" / "masked"


def masked_sprite(data: bytes, width_bytes: int, height: int) -> Image.Image:
    w = width_bytes * 8
    img = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    row_size = width_bytes * 2
    for y in range(height):
        row = data[y * row_size : (y + 1) * row_size]
        if len(row) < row_size:
            break
        mask = row[:width_bytes]
        pix = row[width_bytes:row_size]
        for bx in range(width_bytes):
            for bit in range(8):
                x = bx * 8 + bit
                m = (mask[bx] >> (7 - bit)) & 1
                p = (pix[bx] >> (7 - bit)) & 1
                if m and p:
                    img.putpixel((x, y), (0, 0, 0, 255))
    return img


def score(img: Image.Image) -> float:
    w, h = img.size
    pixels = list(img.getdata())
    opaque = sum(1 for p in pixels if p[3] > 0)
    if opaque < 12 or opaque > w * h * 0.7:
        return 0.0
    return opaque / (w * h) * min(h / 24.0, 2.0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ram = load_z80(SNAP)
    picks: list[tuple[int, float, Image.Image]] = []
    for width_bytes in (2, 3):
        for height in (24, 32, 40, 48):
            row_size = width_bytes * 2
            total = row_size * height
            for addr in range(0x8000, 0xF000 - total):
                chunk = bytes(ram[addr : addr + total])
                if chunk.count(0) > total * 0.8:
                    continue
                img = masked_sprite(chunk, width_bytes, height)
                s = score(img)
                if s <= 0:
                    continue
                picks.append((addr, s, img))
    picks.sort(key=lambda t: t[1], reverse=True)
    used: set[int] = set()
    saved = 0
    lines = ["# Masked sprite candidates", ""]
    for addr, s, img in picks:
        if any(abs(addr - u) < 64 for u in used):
            continue
        used.add(addr)
        path = OUT / f"masked_0x{addr:04X}_score{s:.3f}.png"
        img.save(path)
        lines.append(f"- 0x{addr:04X} score={s:.3f} {img.size[0]}x{img.size[1]}")
        saved += 1
        if saved >= 48:
            break
    (OUT / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {saved} masked candidates to {OUT}")


if __name__ == "__main__":
    main()
