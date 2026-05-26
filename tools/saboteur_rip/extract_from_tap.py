#!/usr/bin/env python3
"""Extract Saboteur (1985) character sprites from SABOTEU1.TAP into ripped/."""

from __future__ import annotations

import re
import struct
from pathlib import Path

from PIL import Image

from extract_from_disasm import (
    SPRITES,
    SPRITE_H,
    SPRITE_W,
    TILE_BASE,
    TILE_BYTES,
    TILE_COUNT,
    parse_asm_bytes,
    parse_sprite,
    render_sprite,
    upscale,
)

ROOT = Path(__file__).resolve().parents[2]
TAP = ROOT / "assets" / "reference" / "original" / "SABOTEU1.TAP"
ASM = ROOT / "assets" / "reference" / "original" / "sabot1core.asm"
OUT = ROOT / "assets" / "reference" / "original" / "ripped"

TILE_BYTES_TOTAL = TILE_COUNT * TILE_BYTES
SPRITE_BYTES = SPRITE_W * SPRITE_H


def parse_tap_blocks(path: Path) -> tuple[bytearray, list[str]]:
    """Load Saboteur multi-block TAP into a 64K RAM image."""
    data = path.read_bytes()
    pos = 0
    blocks: list[bytes] = []
    log: list[str] = []
    while pos + 2 <= len(data):
        length = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        if length == 0:
            break
        blocks.append(data[pos : pos + length])
        pos += length

    ram = bytearray(0x10000)
    pending_header: bytes | None = None
    for block in blocks:
        if not block:
            continue
        flag = block[0]
        if flag == 0x00:
            name = bytes(block[1:11]).decode("ascii", errors="replace").strip(" \x00")
            data_len = struct.unpack_from("<H", block, 11)[0]
            load_addr = struct.unpack_from("<H", block, 13)[0]
            log.append(f"header {name!r} len={data_len} load=${load_addr:04X}")
            pending_header = block
            continue
        if flag != 0xFF:
            raise ValueError(f"Unknown TAP flag: {flag:#x}")
        if pending_header is None:
            raise ValueError("Data block without header")
        declared_len = struct.unpack_from("<H", pending_header, 11)[0]
        load_addr = struct.unpack_from("<H", pending_header, 13)[0]
        chunk = block[1:-1]
        end = min(0x10000, load_addr + len(chunk))
        ram[load_addr:end] = chunk[: end - load_addr]
        note = ""
        if declared_len != len(chunk):
            note = f" (header len={declared_len})"
        log.append(f"  -> loaded {len(chunk)} bytes at ${load_addr:04X}{note}")
        pending_header = None
    return ram, log


def label_address(label: str) -> int:
    if not label.startswith("L"):
        raise ValueError(label)
    return int(label[1:], 16)


def read_sprite_rows_from_ram(ram: bytearray, addr: int) -> list[list[int]]:
    raw = bytes(ram[addr : addr + SPRITE_BYTES])
    rows: list[list[int]] = []
    for y in range(SPRITE_H):
        rows.append(list(raw[y * SPRITE_W : (y + 1) * SPRITE_W]))
    return rows


def resolve_sprite_rows(
    ram: bytearray, label: str, asm_text: str
) -> tuple[list[list[int]], str]:
    asm_rows = parse_sprite(asm_text, label)
    asm_bytes = bytes(v for row in asm_rows for v in row)

    # TAP multi-load does not place data at disasm ORG addresses; locate maps by signature.
    idx = bytes(ram).find(asm_bytes)
    if idx >= 0:
        return read_sprite_rows_from_ram(ram, idx), f"TAP RAM ${idx:04X}"

    addr = label_address(label)
    direct = bytes(ram[addr : addr + SPRITE_BYTES])
    if direct == asm_bytes:
        return asm_rows, f"TAP RAM ${addr:04X}"

    return asm_rows, f"{ASM.name} ({label})"


def read_tiles(ram: bytearray, asm_text: str) -> tuple[list[bytes], str]:
    """Tile graphics: use disasm dump (verified). TAP $E700 is present but not byte-identical."""
    tile_blob = parse_asm_bytes(asm_text, "LE700", TILE_BYTES_TOTAL)
    tiles = [tile_blob[i * TILE_BYTES : (i + 1) * TILE_BYTES] for i in range(TILE_COUNT)]
    tap_blob = bytes(ram[TILE_BASE : TILE_BASE + TILE_BYTES_TOTAL])
    tap_note = (
        f"; TAP ${TILE_BASE:04X} also loaded ({sum(1 for b in tap_blob if b)} nz bytes)"
        if sum(1 for b in tap_blob if b) >= TILE_BYTES_TOTAL // 4
        else ""
    )
    return tiles, f"{ASM.name} LE700 {tap_note}".strip()


def main() -> None:
    if not TAP.exists():
        raise SystemExit(f"Missing TAP: {TAP}")
    if not ASM.exists():
        raise SystemExit(f"Missing disasm reference: {ASM}")

    print(f"Parsing {TAP.name}...")
    ram, load_log = parse_tap_blocks(TAP)
    for line in load_log:
        print(f"  {line}")

    asm_text = ASM.read_text(encoding="utf-8", errors="replace")
    tiles, tile_source = read_tiles(ram, asm_text)
    print(f"Tiles: {tile_source}")

    OUT.mkdir(parents=True, exist_ok=True)
    ninja_color = (0, 0, 0, 255)
    guard_color = (0, 0, 216, 255)
    ninja_frames: list[Image.Image] = []
    guard_frames: list[Image.Image] = []
    lines = [
        "# Saboteur (1985) sprites — from SABOTEU1.TAP + sabot1core.asm",
        f"Tiles: {tile_source}",
        "",
    ]

    for label, name in SPRITES:
        rows, map_source = resolve_sprite_rows(ram, label, asm_text)
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
        lines.append(f"- {label} {name} [{map_source}]: {ninja_path.name}, {guard_path.name}")

    def sheet(frames: list[Image.Image]) -> Image.Image:
        fw, fh = frames[0].size
        sheet_img = Image.new("RGBA", (fw * len(frames), fh), (32, 32, 48, 255))
        for i, frame in enumerate(frames):
            sheet_img.paste(frame, (i * fw, 0), frame)
        return sheet_img

    sheet(ninja_frames).save(OUT / "ninja_sheet.png")
    sheet(guard_frames).save(OUT / "guard_sheet.png")
    lines.extend(
        [
            "",
            f"Sheets: ninja_sheet.png ({len(ninja_frames)}), guard_sheet.png ({len(guard_frames)})",
        ]
    )
    (OUT / "README.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Ripped {len(SPRITES)} poses to {OUT}")


if __name__ == "__main__":
    main()
