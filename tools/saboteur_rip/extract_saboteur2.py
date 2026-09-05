#!/usr/bin/env python3
"""Extract original Saboteur II (1987) sprites, items and tiles from MS 0515 disasm.

Source: nzeemin/ms0515-various SABOT2-DISASM. Character/BCHRS bytes are already
ZX MSB-left (matches SpriteRotate/njtiles.png 1:1). Do not bit-reverse them —
reversing mirrors every 8x8 cell and shreds composed sprites into vertical strips.
Items are 32x24 ZX bitmaps + attributes; also ZX-order.
Outputs ripped frames plus in-game Godot sheets at 48x56 / 16x16 / 32x16.
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parents[2]
S2 = ROOT / "assets" / "reference" / "original" / "s2" / "ms0515-various" / "SABOT2-DISASM"
BK_SPR = ROOT / "assets" / "reference" / "original" / "s2" / "bk0011m-saboteur2" / "SpriteRotate"
RIPPED = ROOT / "assets" / "reference" / "original" / "ripped_s2"
SPRITES = ROOT / "assets" / "sprites"
TILESETS = ROOT / "assets" / "tilesets"

SPRITE_W, SPRITE_H, TILE_PX = 6, 7, 8
FW, FH = SPRITE_W * TILE_PX, SPRITE_H * TILE_PX  # 48x56
EMPTY = 0o377

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

NINJA_COLOR = (0, 0, 0, 255)
# Bright yellow reads on outdoor blue paper; cyan on blue is nearly invisible.
GUARD_COLOR = (255, 255, 0, 255)

LABEL_RE = re.compile(r"^([KL][0-7]{5}):")
BYTE_RE = re.compile(r"\.BYTE\s+(.+)$", re.IGNORECASE)


def bitrev(b: int) -> int:
    return int(f"{b:08b}"[::-1], 2)


def parse_octal_bytes(part: str) -> list[int]:
    out: list[int] = []
    for tok in part.split(","):
        tok = tok.strip()
        if not tok:
            continue
        if tok.startswith(";"):
            break
        tok = tok.split(";")[0].strip().rstrip(",")
        if not tok:
            continue
        out.append(int(tok, 8))
    return out


def parse_mac_blocks(path: Path) -> dict[str, list[int]]:
    blocks: dict[str, list[int]] = {}
    current: str | None = None
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.split(";", 1)[0].strip()
        if not line:
            continue
        m = LABEL_RE.match(line)
        if m:
            current = m.group(1)
            blocks[current] = []
            rest = line[m.end() :].strip()
            if ".BYTE" in rest.upper():
                part = rest.split(".BYTE", 1)[-1].split(".byte", 1)[-1]
                blocks[current].extend(parse_octal_bytes(part))
            continue
        if current is None:
            continue
        bm = BYTE_RE.search(line)
        if bm:
            blocks[current].extend(parse_octal_bytes(bm.group(1)))
    return blocks


def pad42(data: list[int]) -> list[int]:
    out = list(data[: SPRITE_W * SPRITE_H])
    while len(out) < SPRITE_W * SPRITE_H:
        out.append(EMPTY)
    return out


def rows_of(data: list[int]) -> list[list[int]]:
    data = pad42(data)
    return [data[y * SPRITE_W : (y + 1) * SPRITE_W] for y in range(SPRITE_H)]


def render_tile(tile: bytes, color: tuple[int, int, int, int], reverse: bool) -> Image.Image:
    img = Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 0))
    for y, raw in enumerate(tile[:8]):
        b = bitrev(raw) if reverse else raw
        for x in range(8):
            if (b >> (7 - x)) & 1:
                img.putpixel((x, y), color)
    return img


def render_sprite(
    rows: list[list[int]],
    tiles: list[bytes],
    color: tuple[int, int, int, int],
    reverse: bool,
) -> Image.Image:
    img = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, code in enumerate(row):
            if code == EMPTY or code >= len(tiles):
                continue
            tile_img = render_tile(tiles[code], color, reverse)
            img.paste(tile_img, (x * TILE_PX, y * TILE_PX), tile_img)
    return img


def ink_tiles_from_sheet(
    path: Path,
    count: int,
    color: tuple[int, int, int, int],
    stride_x: int = 19,
    stride_y: int = 10,
    origin: tuple[int, int] = (8, 8),
) -> list[Image.Image]:
    """8x8 ink tiles from nzeemin SpriteRotate sheets (black = ink, blue/red = paper)."""
    src = Image.open(path).convert("RGBA")
    ox, oy = origin
    tiles: list[Image.Image] = []
    for i in range(count):
        x = ox + (i % 16) * stride_x
        y = oy + (i // 16) * stride_y
        cell = src.crop((x, y, x + TILE_PX, y + TILE_PX))
        tile = Image.new("RGBA", (TILE_PX, TILE_PX), (0, 0, 0, 0))
        for py in range(TILE_PX):
            for px in range(TILE_PX):
                r, g, b, _a = cell.getpixel((px, py))
                if r + g + b < 140:
                    tile.putpixel((px, py), color)
        tiles.append(tile)
    return tiles


def blit_sprite(rows: list[list[int]], tile_imgs: list[Image.Image]) -> Image.Image:
    img = Image.new("RGBA", (FW, FH), (0, 0, 0, 0))
    for y, row in enumerate(rows):
        for x, code in enumerate(row):
            if code == EMPTY or code >= len(tile_imgs):
                continue
            t = tile_imgs[code]
            img.paste(t, (x * TILE_PX, y * TILE_PX), t)
    return img


def upscale(img: Image.Image, scale: int = 1) -> Image.Image:
    if scale == 1:
        return img
    w, h = img.size
    return img.resize((w * scale, h * scale), Image.NEAREST)


def sheet_of(frames: list[Image.Image], bg=(0, 0, 0, 0)) -> Image.Image:
    fw, fh = frames[0].size
    sheet = Image.new("RGBA", (fw * len(frames), fh), bg)
    for i, frame in enumerate(frames):
        sheet.paste(frame, (i * fw, 0), frame)
    return sheet


def spec_color(attr: int, ink: bool) -> tuple[int, int, int, int]:
    bright = (attr >> 6) & 1
    idx = ((attr & 7) if ink else ((attr >> 3) & 7)) + (8 if bright else 0)
    r, g, b = SPEC_PAL[idx]
    return (r, g, b, 255)


def render_bchr(tile9: bytes, reverse: bool) -> Image.Image:
    pix, attr = tile9[:8], tile9[8]
    img = Image.new("RGBA", (TILE_PX, TILE_PX), spec_color(attr, False))
    for y, raw in enumerate(pix):
        b = bitrev(raw) if reverse else raw
        ink = spec_color(attr, True)
        for x in range(8):
            if (b >> (7 - x)) & 1:
                img.putpixel((x, y), ink)
    return img


def render_item(block: list[int], reverse: bool, fill_paper: bool = True) -> Image.Image:
    bitmap = bytes(block[:96])
    attrs = block[96:108]
    img = Image.new("RGBA", (32, 24), (0, 0, 0, 0))
    for y in range(24):
        row = bitmap[y * 4 : (y + 1) * 4]
        attr_row = y // 8
        for bx, raw in enumerate(row):
            b = bitrev(raw) if reverse else raw
            attr = attrs[attr_row * 4 + bx] if attr_row * 4 + bx < len(attrs) else 0x47
            paper = spec_color(attr, False)
            ink = spec_color(attr, True)
            paper_vis = paper[0] | paper[1] | paper[2]
            for x in range(8):
                on = (b >> (7 - x)) & 1
                if on:
                    img.putpixel((bx * 8 + x, y), ink)
                elif fill_paper and paper_vis:
                    img.putpixel((bx * 8 + x, y), paper)
    return img


def compose_run(runc: list[int], leg: list[int]) -> list[int]:
    return pad42(list(runc[:24]) + list(leg[:18]))


def nudge(frame: Image.Image, dy: int = 1) -> Image.Image:
    out = Image.new("RGBA", frame.size, (0, 0, 0, 0))
    out.paste(frame, (0, dy), frame)
    return out


def save_png(path: Path, img: Image.Image) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)


def main() -> None:
    sprt = parse_mac_blocks(S2 / "S2SPRT.MAC")
    nina_maps = parse_mac_blocks(S2 / "S24C72.MAC")
    nina_tiles_blk = parse_mac_blocks(S2 / "S29DE4.MAC")
    items_blk = parse_mac_blocks(S2 / "S2ITEM.MAC")

    ninja_tile_bytes = nina_tiles_blk["L16744"]
    ninja_tiles = [bytes(ninja_tile_bytes[i : i + 8]) for i in range(0, len(ninja_tile_bytes) - 7, 8)]

    # K73550 is GCHRS then unlabeled maps until K76727. Keep 196 ZX 8-byte tiles.
    guard_tile_bytes = sprt["K73550"][: 196 * 8]
    guard_tiles = [bytes(guard_tile_bytes[i : i + 8]) for i in range(0, len(guard_tile_bytes), 8)]

    bchrs: list[bytes] = []
    for key in sorted((k for k in sprt if k >= "K77531" and k < "L04120"), key=lambda s: s):
        block = sprt[key]
        if len(block) == 9:
            bchrs.append(bytes(block))
        elif len(block) >= 9 and len(block) % 9 == 0:
            for i in range(0, len(block), 9):
                bchrs.append(bytes(block[i : i + 9]))

    RIPPED.mkdir(parents=True, exist_ok=True)

    runc = nina_maps["K46756"]
    legs = nina_maps["K47030"]
    leg_frames = [legs[i : i + 18] for i in range(0, 72, 18)]

    ninja_defs: list[tuple[str, list[int]]] = [
        ("standing", nina_maps["K46561"]),
        ("walk_1", compose_run(runc, leg_frames[0])),
        ("walk_2", compose_run(runc, leg_frames[1])),
        ("walk_3", compose_run(runc, leg_frames[2])),
        ("walk_4", compose_run(runc, leg_frames[3])),
        ("punch", nina_maps["K46704"]),
        ("jump", nina_maps["K47336"]),
        ("kick", nina_maps["K47410"][:42]),
        ("kick2", nina_maps["K47410"][42:84] or nina_maps["K47410"][:42]),
        ("ladder", nina_maps["K46632"]),
        ("crouch", nina_maps["K47212"]),
        ("dead", nina_maps["K47534"]),
        ("falling", nina_maps["K47606"]),
    ]

    ninja_frames: list[Image.Image] = []
    # Walk maps face left; idle/jump/punch originally face the opposite way.
    # Mirror every side-view frame so they all face right (flip_h covers left).
    mirror_right = {
        "standing",
        "walk_1",
        "walk_2",
        "walk_3",
        "walk_4",
        "punch",
        "jump",
        "kick",
        "kick2",
        "crouch",
        "dead",
        "falling",
    }
    for name, data in ninja_defs:
        img = render_sprite(rows_of(data), ninja_tiles, NINJA_COLOR, reverse=False)
        if name in mirror_right:
            img = ImageOps.mirror(img)
        save_png(RIPPED / f"nina_{name}.png", img)
        ninja_frames.append(img)

    guard_defs: list[tuple[str, str]] = [
        ("standing", "K77140"),  # ST2GC — feet together
        ("walk_1", "K77067"),  # ST1GC
        ("walk_2", "K77140"),
        ("walk_3", "K77211"),  # ST3GC
        ("walk_4", "K77140"),
        ("punch", "K77333"),
        ("dead", "K77403"),
        ("kick", "K77333"),
    ]
    gdtiles_path = BK_SPR / "gdtiles.png"
    if gdtiles_path.is_file():
        guard_tile_imgs = ink_tiles_from_sheet(gdtiles_path, 196, GUARD_COLOR)
        guard_frames = []
        for name, label in guard_defs:
            img = blit_sprite(rows_of(sprt[label]), guard_tile_imgs)
            save_png(RIPPED / f"s2guard_{name}.png", img)
            guard_frames.append(img)
    else:
        guard_frames = []
        for name, label in guard_defs:
            img = render_sprite(rows_of(sprt[label]), guard_tiles, GUARD_COLOR, reverse=False)
            save_png(RIPPED / f"s2guard_{name}.png", img)
            guard_frames.append(img)

    save_png(RIPPED / "nina_sheet.png", sheet_of(ninja_frames, (32, 32, 48, 255)))
    save_png(RIPPED / "s2guard_sheet.png", sheet_of(guard_frames, (32, 32, 48, 255)))

    # Player in-game sheet: idle×2, run×4, punch×2, jump_kick×2, climb×2, crouch×2
    by_name = {name: img for (name, _), img in zip(ninja_defs, ninja_frames)}
    player_order = [
        "standing",
        "standing",
        "walk_1",
        "walk_2",
        "walk_3",
        "walk_4",
        "punch",
        "punch",
        "jump",
        "kick2",
        "ladder",
        "ladder",
        "crouch",
        "crouch",
    ]
    player_frames = [by_name[n] for n in player_order]
    player_frames[1] = nudge(player_frames[0], 1)
    # Slot 7 is standing high kick (UP+HIT); flying yoko-geri stays on slot 9 (kick2).
    player_frames[7] = by_name["kick"]
    # Opposite limbs; vertical travel is the climb step, not a sprite nudge.
    player_frames[11] = ImageOps.mirror(by_name["ladder"])
    player_frames[13] = nudge(by_name["crouch"], 1)
    player_sheet = sheet_of(player_frames)
    save_png(SPRITES / "saboteur2_player.png", player_sheet)
    save_png(SPRITES / "saboteur93_player.png", player_sheet)
    save_png(SPRITES / "saboteur85_player.png", player_sheet)

    g_by = {name: img for name, img in zip((n for n, _ in guard_defs), guard_frames)}
    guard_order = ["standing", "standing", "walk_1", "walk_2", "walk_3", "walk_4", "punch"]
    guard_sheet = sheet_of([g_by[n] for n in guard_order])
    guard_sheet_out = SPRITES / "saboteur2_guard.png"
    save_png(guard_sheet_out, guard_sheet)
    # Keep legacy filename used by older scenes as a copy
    save_png(SPRITES / "saboteur85_guard.png", guard_sheet)

    # Items are ZX-order in the MS 0515 dump (do not bit-reverse).
    item_labels = ["K05274", "K05450", "K05624", "K06000", "K06154", "K06330", "K06504"]
    item_imgs = [render_item(items_blk[lab], reverse=False) for lab in item_labels if lab in items_blk]
    save_png(RIPPED / "s2_items.png", sheet_of(item_imgs, (0, 0, 0, 255)))
    # Game pickups: wrench=key, mystery ?=document, shuriken=bomb stand-in.
    # Inventory chrome (name bar / paper) is stripped so only the 32x16 icon remains.
    pickup_src = [
        render_item(items_blk[item_labels[i]], reverse=False, fill_paper=False)
        for i in (5, 4, 1)
    ]
    pickup_icons = [im.crop((0, 0, 32, 16)) for im in pickup_src]
    items_sheet = sheet_of(pickup_icons)
    save_png(SPRITES / "saboteur2_items.png", items_sheet)
    save_png(SPRITES / "saboteur85_items.png", items_sheet)

    if bchrs:
        bchr_imgs = [render_bchr(t, reverse=False) for t in bchrs]
        cols = 16
        rows = (len(bchr_imgs) + cols - 1) // cols
        grid = Image.new("RGBA", (cols * 10, rows * 10), (16, 16, 24, 255))
        for i, im in enumerate(bchr_imgs):
            grid.paste(im, ((i % cols) * 10, (i // cols) * 10))
        save_png(RIPPED / "s2_bchrs.png", grid)

        # Matches level_01.gd tile constants: brick, floor, ladder, door, crate, window, ceiling, bg
        chosen = [0, 21, 20, 2, 68, 9, 12, 1]
        tiles = Image.new("RGBA", (16 * 8, 16), (0, 0, 0, 0))
        for i, idx in enumerate(chosen):
            cell = upscale(bchr_imgs[idx], 2)
            tiles.paste(cell, (i * 16, 0))
        # Outdoor S2 sky is bright Spectrum blue so the black ninja silhouette reads.
        for x in range(16 * 7, 16 * 8):
            for y in range(16):
                tiles.putpixel((x, y), (0, 0, 255, 255))
        save_png(TILESETS / "saboteur2_tileset.png", tiles)
        save_png(TILESETS / "saboteur85_tileset.png", tiles)
        (RIPPED / "tileset_indices.txt").write_text(
            "chosen BCHRS indices: " + ",".join(str(i) for i in chosen) + "\n",
            encoding="utf-8",
        )

    print(f"Ninja tiles: {len(ninja_tiles)}")
    print(f"Guard tiles: {len(guard_tiles)}")
    print(f"BCHRS tiles: {len(bchrs)}")
    print(f"Wrote {SPRITES / 'saboteur2_player.png'} ({player_sheet.size})")
    print(f"Wrote {guard_sheet_out} ({guard_sheet.size})")
    print(f"Ripped frames -> {RIPPED}")


if __name__ == "__main__":
    main()
