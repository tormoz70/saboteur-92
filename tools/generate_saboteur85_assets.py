#!/usr/bin/env python3
"""Generate Saboteur! (1985) style assets — faithful ZX-style sprites at 32x48 (2x16x24)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT_SPRITES = ROOT / "assets" / "sprites"
OUT_TILES = ROOT / "assets" / "tilesets"

# ZX Spectrum bright palette (approximate)
BLACK = (0, 0, 0)
BLUE = (0, 0, 216)
BLUE_D = (0, 0, 128)
RED = (216, 0, 0)
RED_D = (160, 0, 0)
CYAN = (0, 216, 216)
YELLOW = (216, 216, 0)
WHITE = (255, 255, 255)
SKIN = (216, 176, 136)
SKIN_D = (184, 140, 104)
BRICK = (200, 0, 0)
BRICK_HI = (255, 72, 72)
FLOOR = (216, 216, 0)
FLOOR_D = (160, 160, 0)
WOOD = (160, 96, 32)
WOOD_D = (96, 56, 16)
GREY = (128, 128, 128)
BG_BLUE = (0, 0, 136)
BG_BLUE_HI = (0, 0, 200)
TRANSPARENT = (0, 0, 0, 0)

BW, BH = 16, 24
W, H = BW * 2, BH * 2


def base_sprite() -> Image.Image:
    return Image.new("RGBA", (BW, BH), TRANSPARENT)


def upscale(img: Image.Image) -> Image.Image:
    return img.resize((W, H), Image.NEAREST)


def px(img: Image.Image, x: int, y: int, color) -> None:
    w, h = img.size
    if 0 <= x < w and 0 <= y < h:
        img.putpixel((x, y), color)


def fill(img: Image.Image, x0: int, y0: int, x1: int, y1: int, color) -> None:
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px(img, x, y, color)


def draw_ninja_hood(img: Image.Image, facing: int = 1) -> None:
    """Classic Saboteur ninja head: black hood + skin eye slit."""
    fill(img, 5, 0, 10, 1, BLACK)
    fill(img, 4, 2, 11, 2, BLACK)
    fill(img, 4, 3, 11, 6, BLACK)
    fill(img, 5, 7, 10, 7, BLACK)
    if facing > 0:
        fill(img, 8, 4, 10, 4, SKIN)
        px(img, 9, 4, BLACK)
    else:
        fill(img, 5, 4, 7, 4, SKIN)
        px(img, 6, 4, BLACK)


def draw_ninja_torso(img: Image.Image) -> None:
    fill(img, 5, 8, 10, 15, BLACK)
    fill(img, 4, 9, 4, 14, BLACK)
    fill(img, 11, 9, 11, 14, BLACK)
    fill(img, 4, 16, 11, 16, RED)


def draw_ninja_idle(img: Image.Image, frame: int) -> None:
    draw_ninja_hood(img)
    draw_ninja_torso(img)
    fill(img, 5, 17, 7, 22, BLACK)
    fill(img, 8, 17, 10, 22, BLACK)
    fill(img, 5, 23, 6, 23, BLACK)
    fill(img, 9, 23, 10, 23, BLACK)
    fill(img, 3, 10, 3, 14, BLACK)
    fill(img, 12, 10, 12, 14, BLACK)
    if frame == 1:
        px(img, 6, 18, BLACK)
        px(img, 9, 19, BLACK)


def draw_ninja_run(img: Image.Image, frame: int) -> None:
    draw_ninja_hood(img)
    draw_ninja_torso(img)
    leg = frame % 4
    if leg in (0, 2):
        fill(img, 4, 17, 6, 20, BLACK)
        fill(img, 8, 19, 10, 23, BLACK)
        fill(img, 8, 23, 9, 23, BLACK)
        fill(img, 2, 11, 3, 15, BLACK)
        fill(img, 12, 12, 13, 16, BLACK)
    else:
        fill(img, 8, 17, 10, 20, BLACK)
        fill(img, 4, 19, 6, 23, BLACK)
        fill(img, 4, 23, 5, 23, BLACK)
        fill(img, 2, 12, 3, 16, BLACK)
        fill(img, 12, 11, 13, 15, BLACK)


def draw_ninja_jump(img: Image.Image) -> None:
    draw_ninja_hood(img)
    fill(img, 5, 8, 10, 14, BLACK)
    fill(img, 4, 16, 11, 16, RED)
    fill(img, 3, 10, 3, 13, BLACK)
    fill(img, 12, 10, 12, 13, BLACK)
    fill(img, 4, 17, 6, 19, BLACK)
    fill(img, 8, 17, 10, 19, BLACK)
    fill(img, 2, 18, 4, 20, BLACK)
    fill(img, 11, 18, 13, 20, BLACK)


def draw_ninja_punch(img: Image.Image, frame: int) -> None:
    draw_ninja_hood(img)
    draw_ninja_torso(img)
    fill(img, 5, 17, 7, 22, BLACK)
    fill(img, 8, 17, 10, 22, BLACK)
    fill(img, 5, 23, 6, 23, BLACK)
    fill(img, 9, 23, 10, 23, BLACK)
    if frame == 0:
        fill(img, 12, 10, 14, 11, BLACK)
        fill(img, 14, 11, 15, 12, SKIN)
    else:
        fill(img, 12, 9, 15, 10, BLACK)
        fill(img, 14, 10, 15, 12, SKIN)


def draw_ninja_kick(img: Image.Image) -> None:
    """Saboteur-style jump kick (used as punch animation frame 2)."""
    draw_ninja_hood(img)
    fill(img, 5, 8, 10, 14, BLACK)
    fill(img, 4, 16, 11, 16, RED)
    fill(img, 3, 10, 3, 13, BLACK)
    fill(img, 5, 17, 7, 20, BLACK)
    fill(img, 8, 19, 10, 21, BLACK)
    fill(img, 11, 20, 15, 21, BLACK)
    fill(img, 14, 21, 15, 22, BLACK)


def draw_ninja_climb(img: Image.Image, frame: int) -> None:
    draw_ninja_hood(img)
    draw_ninja_torso(img)
    if frame == 0:
        fill(img, 3, 10, 4, 15, BLACK)
        fill(img, 11, 11, 12, 16, BLACK)
        fill(img, 5, 17, 6, 23, BLACK)
        fill(img, 9, 19, 10, 23, BLACK)
    else:
        fill(img, 3, 11, 4, 16, BLACK)
        fill(img, 11, 10, 12, 15, BLACK)
        fill(img, 9, 17, 10, 23, BLACK)
        fill(img, 5, 19, 6, 23, BLACK)


def draw_ninja_death(img: Image.Image) -> None:
    fill(img, 2, 18, 13, 20, BLACK)
    fill(img, 4, 17, 11, 17, BLACK)
    fill(img, 11, 17, 12, 17, SKIN)
    fill(img, 1, 20, 3, 20, BLACK)
    fill(img, 12, 20, 14, 20, BLACK)


def draw_guard(img: Image.Image, pose: str, frame: int = 0) -> None:
    """Original Saboteur guard: red beret, skin face, blue uniform, black boots."""
    fill(img, 4, 0, 11, 2, RED)
    fill(img, 5, 3, 10, 3, RED_D)
    fill(img, 5, 4, 10, 8, SKIN)
    px(img, 8, 6, BLACK)
    fill(img, 6, 7, 9, 7, SKIN_D)
    fill(img, 4, 9, 11, 19, BLUE)
    fill(img, 6, 10, 9, 11, WHITE)
    px(img, 7, 12, YELLOW)
    px(img, 8, 12, YELLOW)
    px(img, 7, 14, YELLOW)
    px(img, 8, 14, YELLOW)
    fill(img, 4, 19, 11, 19, BLACK)
    fill(img, 5, 20, 7, 23, BLACK)
    fill(img, 8, 20, 10, 23, BLACK)

    if pose == "idle":
        fill(img, 5, 20, 7, 22, BLACK)
        fill(img, 8, 20, 10, 22, BLACK)
        fill(img, 3, 11, 3, 16, BLUE)
        fill(img, 12, 11, 12, 16, BLUE)
        if frame == 1:
            px(img, 6, 21, BLUE_D)
            px(img, 9, 21, BLUE_D)
    elif pose == "run":
        leg = frame % 4
        if leg in (0, 2):
            fill(img, 5, 20, 6, 22, BLACK)
            fill(img, 9, 21, 10, 23, BLACK)
            fill(img, 2, 12, 2, 16, BLUE)
            fill(img, 13, 11, 13, 15, BLUE)
        else:
            fill(img, 9, 20, 10, 22, BLACK)
            fill(img, 5, 21, 6, 23, BLACK)
            fill(img, 2, 11, 2, 15, BLUE)
            fill(img, 13, 12, 13, 16, BLUE)
    elif pose == "punch":
        fill(img, 5, 20, 7, 22, BLACK)
        fill(img, 8, 20, 10, 22, BLACK)
        fill(img, 3, 11, 3, 15, BLUE)
        fill(img, 12, 11, 15, 12, BLUE)
        fill(img, 14, 12, 15, 13, SKIN)
        fill(img, 13, 13, 14, 13, BLACK)


def blit(sheet: Image.Image, frame: Image.Image, index: int) -> None:
    sheet.paste(frame, (index * W, 0), frame)


def frame_upscaled(draw_fn, *args) -> Image.Image:
    img = base_sprite()
    draw_fn(img, *args)
    return upscale(img)


def build_player_sheet() -> Image.Image:
    frames: list[Image.Image] = []
    for i in range(2):
        frames.append(frame_upscaled(draw_ninja_idle, i))
    for i in range(4):
        frames.append(frame_upscaled(draw_ninja_run, i))
    frames.append(frame_upscaled(draw_ninja_jump))
    frames.append(frame_upscaled(draw_ninja_punch, 0))
    img = base_sprite()
    draw_ninja_kick(img)
    frames.append(upscale(img))
    for i in range(2):
        frames.append(frame_upscaled(draw_ninja_climb, i))
    frames.append(frame_upscaled(draw_ninja_death))
    sheet = Image.new("RGBA", (W * len(frames), H), TRANSPARENT)
    for i, frame in enumerate(frames):
        blit(sheet, frame, i)
    return sheet


def build_guard_sheet() -> Image.Image:
    frames: list[Image.Image] = []
    for i in range(2):
        frames.append(frame_upscaled(draw_guard, "idle", i))
    for i in range(4):
        frames.append(frame_upscaled(draw_guard, "run", i))
    frames.append(frame_upscaled(draw_guard, "punch"))
    sheet = Image.new("RGBA", (W * len(frames), H), TRANSPARENT)
    for i, frame in enumerate(frames):
        blit(sheet, frame, i)
    return sheet


def build_item_sprite(kind: str) -> Image.Image:
    img = Image.new("RGBA", (24, 24), TRANSPARENT)
    if kind == "key":
        fill(img, 10, 3, 13, 12, YELLOW)
        fill(img, 7, 12, 16, 14, YELLOW)
        fill(img, 5, 15, 7, 16, YELLOW)
        fill(img, 4, 17, 6, 18, YELLOW)
    elif kind == "document":
        fill(img, 6, 3, 17, 20, WHITE)
        fill(img, 6, 3, 17, 4, CYAN)
        for y in range(7, 18, 3):
            fill(img, 8, y, 15, y, CYAN)
    elif kind == "bomb":
        fill(img, 8, 6, 15, 19, BLACK)
        fill(img, 9, 3, 14, 5, RED)
        fill(img, 10, 1, 13, 2, YELLOW)
    return img


def build_items_sheet() -> Image.Image:
    items = ["key", "document", "bomb"]
    sheet = Image.new("RGBA", (24 * len(items), 24), TRANSPARENT)
    for i, kind in enumerate(items):
        sheet.paste(build_item_sprite(kind), (i * 24, 0))
    return sheet


def tile_brick() -> Image.Image:
    t = Image.new("RGBA", (16, 16), BLACK)
    for y in range(16):
        for x in range(16):
            row = y // 4
            col = (x + (4 if row % 2 else 0)) // 4
            t.putpixel((x, y), BRICK if (row + col) % 2 == 0 else BRICK_HI)
    for y in range(0, 16, 4):
        for x in range(16):
            px(t, x, y, BLACK)
    return t


def tile_floor() -> Image.Image:
    t = Image.new("RGBA", (16, 16), FLOOR)
    for y in range(0, 16, 2):
        for x in range(16):
            px(t, x, y, FLOOR_D)
    return t


def tile_ladder() -> Image.Image:
    t = Image.new("RGBA", (16, 16), TRANSPARENT)
    fill(t, 2, 0, 3, 15, BLACK)
    fill(t, 12, 0, 13, 15, BLACK)
    for y in range(2, 16, 4):
        fill(t, 3, y, 12, y + 1, YELLOW)
    return t


def tile_door() -> Image.Image:
    t = Image.new("RGBA", (16, 16), WOOD_D)
    fill(t, 2, 1, 13, 14, WOOD)
    px(t, 11, 8, YELLOW)
    return t


def tile_crate() -> Image.Image:
    t = Image.new("RGBA", (16, 16), WOOD_D)
    fill(t, 1, 2, 14, 14, YELLOW)
    fill(t, 1, 2, 14, 2, WOOD_D)
    fill(t, 1, 14, 14, 14, WOOD_D)
    fill(t, 1, 8, 14, 8, WOOD_D)
    return t


def tile_window() -> Image.Image:
    t = tile_brick()
    fill(t, 4, 4, 11, 10, CYAN)
    fill(t, 7, 4, 8, 10, BLACK)
    fill(t, 4, 6, 11, 7, BLACK)
    return t


def tile_ceiling() -> Image.Image:
    t = Image.new("RGBA", (16, 16), GREY)
    for x in range(16):
        px(t, x, 0, BLACK)
    return t


def tile_background() -> Image.Image:
    t = Image.new("RGBA", (16, 16), BG_BLUE)
    for y in range(16):
        for x in range(16):
            if (x + y) % 4 == 0:
                px(t, x, y, BG_BLUE_HI)
    return t


def build_tileset() -> Image.Image:
    tiles = [tile_brick(), tile_floor(), tile_ladder(), tile_door(), tile_crate(), tile_window(), tile_ceiling(), tile_background()]
    sheet = Image.new("RGBA", (16 * len(tiles), 16), TRANSPARENT)
    for i, tile in enumerate(tiles):
        sheet.paste(tile, (i * 16, 0))
    return sheet


def main() -> None:
    OUT_SPRITES.mkdir(parents=True, exist_ok=True)
    OUT_TILES.mkdir(parents=True, exist_ok=True)
    player_path = OUT_SPRITES / "saboteur85_player.png"
    guard_path = OUT_SPRITES / "saboteur85_guard.png"
    items_path = OUT_SPRITES / "saboteur85_items.png"
    tileset_path = OUT_TILES / "saboteur85_tileset.png"
    build_player_sheet().save(player_path)
    build_guard_sheet().save(guard_path)
    build_items_sheet().save(items_path)
    build_tileset().save(tileset_path)
    print(f"Wrote {player_path} (32x48 frames)")
    print(f"Wrote {guard_path}")
    print(f"Wrote {items_path} (24x24 items)")


if __name__ == "__main__":
    main()
