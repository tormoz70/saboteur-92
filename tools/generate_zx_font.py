#!/usr/bin/env python3
"""Build the 8x8 ZX font used by the menus from the Saboteur II disassembly.

Source: assets/reference/original/s2/bk0011m-saboteur2/S2FONT.MAC, the game's
own character set (ASCII 32..127, one octal byte per row, MSB is the left
pixel). Output: assets/ui/zx_font.png (white glyphs on transparent) and
assets/ui/zx_font.fnt (BMFont text), which Godot imports as a bitmap font.

Deterministic, stdlib only (re, struct, zlib, pathlib). The font has no
Cyrillic, so menu text stays in English.
"""

from __future__ import annotations

import re
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "assets" / "reference" / "original" / "s2" / "bk0011m-saboteur2" / "S2FONT.MAC"
OUT_DIR = ROOT / "assets" / "ui"
PNG_NAME = "zx_font.png"
FNT_NAME = "zx_font.fnt"

FIRST_CHAR = 32
GLYPH = 8
# One transparent pixel around every glyph so scaled sampling never bleeds.
CELL = GLYPH + 2
COLS = 16


def read_glyphs() -> list[list[int]]:
    text = SRC.read_text(encoding="ascii")
    values: list[int] = []
    for line in text.splitlines():
        m = re.search(r"\.BYTE\s+(.*)", line)
        if m:
            values.extend(int(v, 8) for v in m.group(1).split(","))
    if len(values) % GLYPH:
        raise SystemExit(f"{SRC.name}: {len(values)} bytes is not a whole number of glyphs")
    return [values[i : i + GLYPH] for i in range(0, len(values), GLYPH)]


def build_png(glyphs: list[list[int]]) -> tuple[bytes, int, int]:
    rows = (len(glyphs) + COLS - 1) // COLS
    width = COLS * CELL
    height = rows * CELL
    pixels = bytearray(width * height * 4)
    for index, glyph in enumerate(glyphs):
        ox = (index % COLS) * CELL + 1
        oy = (index // COLS) * CELL + 1
        for y, bits in enumerate(glyph):
            for x in range(GLYPH):
                if bits & (0x80 >> x):
                    p = ((oy + y) * width + ox + x) * 4
                    pixels[p : p + 4] = b"\xff\xff\xff\xff"
    raw = b"".join(
        b"\x00" + bytes(pixels[y * width * 4 : (y + 1) * width * 4]) for y in range(height)
    )

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw, 9))
        + chunk(b"IEND", b"")
    )
    return png, width, height


def build_fnt(glyphs: list[list[int]], width: int, height: int) -> str:
    lines = [
        'info face="ZX Saboteur" size=8 bold=0 italic=0 charset="" unicode=1 '
        "stretchH=100 smooth=0 aa=1 padding=0,0,0,0 spacing=0,0 outline=0",
        f"common lineHeight={GLYPH} base={GLYPH - 1} scaleW={width} scaleH={height} "
        "pages=1 packed=0 alphaChnl=0 redChnl=0 greenChnl=0 blueChnl=0",
        f'page id=0 file="{PNG_NAME}"',
        f"chars count={len(glyphs)}",
    ]
    for index in range(len(glyphs)):
        x = (index % COLS) * CELL + 1
        y = (index // COLS) * CELL + 1
        lines.append(
            f"char id={FIRST_CHAR + index} x={x} y={y} width={GLYPH} height={GLYPH} "
            f"xoffset=0 yoffset=0 xadvance={GLYPH} page=0 chnl=15"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    glyphs = read_glyphs()
    png, width, height = build_png(glyphs)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / PNG_NAME).write_bytes(png)
    (OUT_DIR / FNT_NAME).write_text(build_fnt(glyphs, width, height), encoding="ascii", newline="\n")
    print(f"generate_zx_font: {len(glyphs)} glyphs -> {OUT_DIR / PNG_NAME} ({width}x{height})")


if __name__ == "__main__":
    main()
