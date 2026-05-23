#!/usr/bin/env python3
"""Extract Spectrum screen and hunt 1bpp sprite blobs from a .z80 snapshot."""

from __future__ import annotations

import struct
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "assets" / "reference" / "original" / "snap" / "SABOTEUR.Z80"
OUT = ROOT / "assets" / "reference" / "original" / "extracted"

# ZX Spectrum bright palette (approx)
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


def decompress_block(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        b = data[i]
        i += 1
        if b != 0xED:
            out.append(b)
            continue
        if i >= len(data) or data[i] != 0xA3:
            out.extend(data[i - 1 : i])
            continue
        i += 1
        if i + 1 >= len(data):
            break
        count = data[i]
        val = data[i + 1]
        i += 2
        out.extend([val] * count)
    return bytes(out)


def load_z80(path: Path) -> bytearray:
    raw = path.read_bytes()
    if len(raw) < 30:
        raise ValueError("Z80 file too small")
    ram = bytearray(0x10000)
    if raw[30] != 0xFF:
        block = raw[30:]
        if len(block) >= 49152:
            ram[0x4000:0x4000 + 49152] = block[:49152]
        else:
            ram[0x4000:0x4000 + len(block)] = block
        return ram

    add_len = struct.unpack("<H", raw[31:33])[0]
    pos = 32 + add_len
    while pos + 4 <= len(raw):
        length = struct.unpack("<H", raw[pos : pos + 2])[0]
        pos += 2
        offset = struct.unpack("<H", raw[pos : pos + 2])[0]
        pos += 2
        if length == 0xFFFF:
            break
        if pos + length > len(raw):
            break
        block = raw[pos : pos + length]
        pos += length
        if length == 0x4000:
            ram[offset : offset + 0x4000] = block
        else:
            data = decompress_block(block)
            end = min(offset + len(data), 0x10000)
            ram[offset:end] = data[: end - offset]
    return ram


def render_screen(ram: bytearray) -> Image.Image:
    img = Image.new("RGB", (256, 192), (0, 0, 0))
    px = img.load()
    for y in range(192):
        for x in range(256):
            byte_x = x // 8
            bit = 7 - (x % 8)
            addr = 0x4000 + ((y & 0xC0) << 5) | ((y & 0x07) << 8) | ((y & 0x38) << 2) | byte_x
            ink = (ram[addr] >> bit) & 1
            attr_addr = 0x5800 + (y // 8) * 32 + byte_x
            attr = ram[attr_addr]
            paper = (attr >> 3) & 7
            bright = (attr >> 6) & 1
            color_idx = paper + (8 if bright else 0)
            if ink:
                color_idx = (attr & 7) + (8 if bright else 0)
            px[x, y] = SPEC_PAL[color_idx]
    return img


def bitmap_from_bytes(data: bytes, width_bytes: int, height: int) -> Image.Image:
    w = width_bytes * 8
    img = Image.new("RGBA", (w, height), (0, 0, 0, 0))
    for y in range(height):
        for bx in range(width_bytes):
            b = data[y * width_bytes + bx] if y * width_bytes + bx < len(data) else 0
            for bit in range(8):
                if b & (1 << (7 - bit)):
                    img.putpixel((bx * 8 + bit, y), (0, 0, 0, 255))
    return img


def score_sprite(data: bytes, width_bytes: int, height: int) -> float:
    if len(data) < width_bytes * height:
        return 0.0
    total = width_bytes * height
    ones = sum(bin(b).count("1") for b in data[:total])
    density = ones / (total * 8)
    if density < 0.08 or density > 0.65:
        return 0.0
    # Prefer compact vertical silhouettes (humanoid-ish)
    return density * (1.0 + min(height / 24.0, 2.0))


def hunt_sprites(ram: bytearray, width_bytes: int, height: int, top_n: int = 40) -> list[tuple[int, float, bytes]]:
    size = width_bytes * height
    hits: list[tuple[int, float, bytes]] = []
    for addr in range(0x6000, 0xF000 - size):
        chunk = bytes(ram[addr : addr + size])
        if chunk.count(0) == len(chunk):
            continue
        s = score_sprite(chunk, width_bytes, height)
        if s <= 0:
            continue
        hits.append((addr, s, chunk))
    hits.sort(key=lambda t: t[1], reverse=True)
    # De-duplicate overlapping addresses
    picked: list[tuple[int, float, bytes]] = []
    used: set[int] = set()
    for addr, s, chunk in hits:
        if any(abs(addr - u) < size for u in used):
            continue
        used.add(addr)
        picked.append((addr, s, chunk))
        if len(picked) >= top_n:
            break
    return picked


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not SNAP.exists():
        raise SystemExit(f"Missing snapshot: {SNAP}")

    ram = load_z80(SNAP)
    screen = render_screen(ram)
    screen.save(OUT / "snapshot_screen.png")
    print(f"Wrote {OUT / 'snapshot_screen.png'}")

    # Common Saboteur-ish sizes: ~16x24 to 16x48 pixels (2x1 or 2x2 bytes wide)
    configs = [(2, 24), (2, 32), (2, 48), (3, 24), (3, 32)]
    sheet_parts: list[Image.Image] = []
    meta_lines = ["# Saboteur Z80 sprite candidates (dev reference only)", ""]

    for width_bytes, height in configs:
        hits = hunt_sprites(ram, width_bytes, height, top_n=24)
        meta_lines.append(f"## {width_bytes * 8}x{height} ({len(hits)} picks)")
        for i, (addr, score, chunk) in enumerate(hits):
            img = bitmap_from_bytes(chunk, width_bytes, height)
            path = OUT / f"candidate_{width_bytes}x8_x{height}_0x{addr:04X}_{i:02d}.png"
            img.save(path)
            meta_lines.append(f"- 0x{addr:04X} score={score:.3f} -> {path.name}")
            sheet_parts.append(img)
        meta_lines.append("")

    if sheet_parts:
        cols = 8
        rows = (len(sheet_parts) + cols - 1) // cols
        cell_w = max(im.width for im in sheet_parts)
        cell_h = max(im.height for im in sheet_parts)
        sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (32, 32, 32, 255))
        for idx, im in enumerate(sheet_parts):
            x = (idx % cols) * cell_w
            y = (idx // cols) * cell_h
            sheet.paste(im, (x, y), im)
        sheet.save(OUT / "candidates_sheet.png")
        print(f"Wrote {OUT / 'candidates_sheet.png'}")

    (OUT / "README.txt").write_text("\n".join(meta_lines), encoding="utf-8")
    print(f"Wrote {OUT / 'README.txt'}")


if __name__ == "__main__":
    main()
