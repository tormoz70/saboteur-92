#!/usr/bin/env python3
"""Try split-block (gfx then mask) sprite layout from Z80 RAM."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from extract_from_z80 import SNAP, load_z80

OUT = Path(__file__).resolve().parents[2] / "assets" / "reference" / "original" / "extracted" / "split"


def render(gfx: bytes, mask: bytes, width_bytes: int, height: int) -> Image.Image:
    w = width_bytes * 8
    img = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    for y in range(height):
        for bx in range(width_bytes):
            g = gfx[y * width_bytes + bx]
            m = mask[y * width_bytes + bx]
            for bit in range(8):
                x = bx * 8 + bit
                if (m >> (7 - bit)) & 1 and (g >> (7 - bit)) & 1:
                    img.putpixel((x, y), (0, 0, 0, 255))
    return img


def score(img: Image.Image) -> float:
    w, h = img.size
    opaque = sum(1 for px in img.get_flattened_data() if px[3] > 0)
    if opaque < 20 or opaque > w * h * 0.75:
        return 0.0
    return opaque / (w * h) * min(h / 24.0, 2.0)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    ram = load_z80(SNAP)
    picks: list[tuple[int, float, Image.Image]] = []
    for width_bytes in (2, 3):
        for height in (24, 32, 40, 48):
            total = width_bytes * height * 2
            for addr in range(0x8000, 0xF000 - total, 2):
                chunk = bytes(ram[addr : addr + total])
                gfx = chunk[: width_bytes * height]
                mask = chunk[width_bytes * height : total]
                img = render(gfx, mask, width_bytes, height)
                s = score(img)
                if s > 0:
                    picks.append((addr, s, img))
    picks.sort(key=lambda t: t[1], reverse=True)
    used: set[int] = set()
    lines = ["# Split-block sprite candidates", ""]
    n = 0
    for addr, s, img in picks:
        if any(abs(addr - u) < 96 for u in used):
            continue
        used.add(addr)
        path = OUT / f"split_0x{addr:04X}_{img.width}x{img.height}.png"
        img.save(path)
        lines.append(f"- 0x{addr:04X} score={s:.3f} -> {path.name}")
        n += 1
        if n >= 40:
            break
    (OUT / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Saved {n} split candidates to {OUT}")


if __name__ == "__main__":
    main()
