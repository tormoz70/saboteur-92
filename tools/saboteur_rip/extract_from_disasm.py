#!/usr/bin/env python3
"""Extract original Saboteur (1985) ninja/guard sprites from sabot1core.asm disassembly."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
ASM = ROOT / "assets" / "reference" / "original" / "sabot1core.asm"
OUT = ROOT / "assets" / "reference" / "original" / "ripped"

TILE_BASE = 0xE700
TILE_BYTES = 16
TILE_COUNT = 159
SPRITE_W = 6
SPRITE_H = 7
TILE_PX = 8

# (label, display name)
SPRITES: list[tuple[str, str]] = [
    ("LD486", "standing"),
    ("LD3DE", "walk_1"),
    ("LD408", "walk_2"),
    ("LD432", "walk_3"),
    ("LD45C", "walk_4"),
    ("LD4B0", "jump"),
    ("LD4DA", "jump_kick"),
    ("LD504", "punch"),
    ("LD52E", "ladder"),
    ("LD582", "falling"),
    ("LD558", "sitting"),
    ("LA0B5", "dead"),
]

GUARD_MAP: dict[int, int] = {
    0x50: 0xC7,
    0x51: 0xDC,
    0x54: 0xDD,
    0xEA: 0xDE,
    0x13: 0xDF,
    0x15: 0xE0,
    0x16: 0xE1,
    0x00: 0xE2,
    0x01: 0xE3,
    0x03: 0xE4,
    0x04: 0xE5,
    0x4D: 0xE6,
    0x22: 0xE7,
    0x2F: 0xE8,
    0x30: 0xE9,
    0xF4: 0xE2,
    0xF5: 0xE3,
    0xF6: 0xE5,
}


def parse_byte(token: str) -> int:
    token = token.strip().rstrip(",")
    if token.startswith("$"):
        return int(token[1:], 16)
    if token.startswith("0x"):
        return int(token, 16)
    raise ValueError(f"Bad byte token: {token}")


def parse_asm_bytes(text: str, start_label: str, byte_count: int) -> bytes:
    lines = text.splitlines()
    collecting = False
    out: list[int] = []
    label_re = re.compile(rf"^{re.escape(start_label)}:")
    for line in lines:
        if label_re.match(line.strip()):
            collecting = True
            if "DEFB" in line or "DEFM" in line:
                part = line.split("DEFB", 1)[-1].split("DEFM", 1)[-1]
                for tok in part.split(","):
                    tok = tok.strip()
                    if tok.startswith("$") or tok.startswith("0x"):
                        out.append(parse_byte(tok))
            continue
        if not collecting:
            continue
        stripped = line.strip()
        if not stripped or stripped.startswith(";"):
            continue
        if re.match(r"^[A-Z][0-9A-F]{4}:", stripped):
            break
        if "DEFB" in stripped:
            part = stripped.split("DEFB", 1)[1]
            for tok in part.split(","):
                tok = tok.strip()
                if tok.startswith("$") or tok.startswith("0x"):
                    out.append(parse_byte(tok))
        if len(out) >= byte_count:
            break
    if len(out) < byte_count:
        raise ValueError(f"{start_label}: expected {byte_count} bytes, got {len(out)}")
    return bytes(out[:byte_count])


def parse_sprite(text: str, label: str) -> list[list[int]]:
    data = parse_asm_bytes(text, label, SPRITE_W * SPRITE_H)
    rows: list[list[int]] = []
    for y in range(SPRITE_H):
        row = list(data[y * SPRITE_W : (y + 1) * SPRITE_W])
        rows.append(row)
    return rows


def resolve_tile(code: int, guard: bool) -> int | None:
    if code == 0xFF:
        return None
    if guard:
        code = GUARD_MAP.get(code, code)
    if code >= 0x80:
        code -= 0x80
    if code >= TILE_COUNT:
        return None
    return code


def render_tile(tile_data: bytes, color: tuple[int, int, int, int]) -> Image.Image:
    """Each scanline is (pixel_byte, mask_byte); draw set pixel bits."""
    img = Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 0))
    for y in range(TILE_PX):
        pix = tile_data[y * 2]
        for x in range(TILE_PX):
            if (pix >> (7 - x)) & 1:
                img.putpixel((x, y), color)
    return img


def render_sprite(
    rows: list[list[int]],
    tiles: list[bytes],
    color: tuple[int, int, int, int],
    guard: bool,
) -> Image.Image:
    w = SPRITE_W * TILE_PX
    h = SPRITE_H * TILE_PX
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, code in enumerate(row):
            idx = resolve_tile(code, guard)
            if idx is None:
                continue
            tile_img = render_tile(tiles[idx], color)
            img.paste(tile_img, (x * TILE_PX, y * TILE_PX), tile_img)
    return img


def upscale(img: Image.Image, scale: int = 2) -> Image.Image:
    w, h = img.size
    out = img.resize((w * scale, h * scale), Image.NEAREST)
    return out


def main() -> None:
    if not ASM.exists():
        raise SystemExit(f"Missing {ASM}")
    text = ASM.read_text(encoding="utf-8", errors="replace")
    tile_blob = parse_asm_bytes(text, "LE700", TILE_COUNT * TILE_BYTES)
    tiles = [tile_blob[i * TILE_BYTES : (i + 1) * TILE_BYTES] for i in range(TILE_COUNT)]

    OUT.mkdir(parents=True, exist_ok=True)
    ninja_color = (0, 0, 0, 255)
    guard_color = (0, 0, 216, 255)

    ninja_frames: list[Image.Image] = []
    guard_frames: list[Image.Image] = []
    lines = [
        "# Saboteur (1985) original sprites — dev reference only",
        f"Source: {ASM.name} (nzeemin/spectrum-saboteur1-rev)",
        f"Format: {SPRITE_W}x{SPRITE_H} tiles @ {TILE_PX}px => {SPRITE_W * TILE_PX}x{SPRITE_H * TILE_PX}px",
        "",
    ]

    for label, name in SPRITES:
        rows = parse_sprite(text, label)
        ninja = render_sprite(rows, tiles, ninja_color, guard=False)
        guard = render_sprite(rows, tiles, guard_color, guard=True)
        ninja_up = upscale(ninja)
        guard_up = upscale(guard)
        ninja_path = OUT / f"ninja_{name}.png"
        guard_path = OUT / f"guard_{name}.png"
        ninja_up.save(ninja_path)
        guard_up.save(guard_path)
        ninja_frames.append(ninja_up)
        guard_frames.append(guard_up)
        lines.append(f"- {label} {name}: {ninja_path.name}, {guard_path.name}")

    def sheet(frames: list[Image.Image]) -> Image.Image:
        fw, fh = frames[0].size
        sheet_img = Image.new("RGBA", (fw * len(frames), fh), (32, 32, 48, 255))
        for i, frame in enumerate(frames):
            sheet_img.paste(frame, (i * fw, 0), frame)
        return sheet_img

    ninja_sheet = sheet(ninja_frames)
    guard_sheet = sheet(guard_frames)
    ninja_sheet.save(OUT / "ninja_sheet.png")
    guard_sheet.save(OUT / "guard_sheet.png")
    lines.extend(["", f"Sheets: ninja_sheet.png ({len(ninja_frames)} frames), guard_sheet.png"])
    (OUT / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Ripped {len(SPRITES)} poses to {OUT}")


if __name__ == "__main__":
    main()
