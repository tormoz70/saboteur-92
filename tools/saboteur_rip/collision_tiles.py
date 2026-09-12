#!/usr/bin/env python3
"""Semantic collision tile grid: empty / solid / ladder / oneway.

Builds assets/world/s2_collision_tiles.json from either live stamp grids
(decompose_world) or the committed s2_collision.json rectangles. Hatch lids
are stored as ladder cells; runtime apply_hatches restores the solid lid.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "assets" / "world"
TILESET_DIR = ROOT / "assets" / "tilesets"
CELL = 8
EMPTY, SOLID, LADDER, ONEWAY = 0, 1, 2, 3
TILE_NAMES = {"empty": EMPTY, "solid": SOLID, "ladder": LADDER, "oneway": ONEWAY}


def rle_encode(indices: list[int]) -> list[int]:
    if not indices:
        return []
    out: list[int] = []
    prev = indices[0]
    count = 1
    for value in indices[1:]:
        if value == prev:
            count += 1
        else:
            out.extend((prev, count))
            prev = value
            count = 1
    out.extend((prev, count))
    return out


def rle_decode(runs: list[int]) -> list[int]:
    out: list[int] = []
    for i in range(0, len(runs), 2):
        out.extend([runs[i]] * runs[i + 1])
    return out


def greedy_rects(grid: list[list[int]], cell: int = CELL) -> list[list[int]]:
    h = len(grid)
    w = len(grid[0]) if h else 0
    seen = [[False] * w for _ in range(h)]
    rects: list[list[int]] = []
    for y in range(h):
        for x in range(w):
            if not grid[y][x] or seen[y][x]:
                continue
            x1 = x
            while x1 < w and grid[y][x1] and not seen[y][x1]:
                x1 += 1
            y1 = y + 1
            grow = True
            while y1 < h and grow:
                for xx in range(x, x1):
                    if not grid[y1][xx] or seen[y1][xx]:
                        grow = False
                        break
                if grow:
                    y1 += 1
            for yy in range(y, y1):
                for xx in range(x, x1):
                    seen[yy][xx] = True
            rects.append([x * cell, y * cell, (x1 - x) * cell, (y1 - y) * cell])
    return rects


def apply_hatches(solid: list[list[int]], ladder: list[list[int]]) -> None:
    ch = len(solid)
    cw = len(solid[0]) if ch else 0
    lids: list[tuple[int, int]] = []
    for y in range(ch):
        for x in range(cw):
            if not ladder[y][x]:
                continue
            for dx in (-1, 1):
                nx = x + dx
                if 0 <= nx < cw and solid[y][nx] and not ladder[y][nx]:
                    lids.append((x, y))
                    break
    for x, y in lids:
        solid[y][x] = 1


def ladder_rects(climb: list[list[int]], cell: int = CELL) -> list[list[int]]:
    rects: list[list[int]] = []
    for x, y, w, h in greedy_rects(climb, cell):
        if h < 24:
            continue
        rects.append([x - 4, y, w + 8, h])
    return rects


def rasterize_rects(
    rects: list, cw: int, ch: int, cell: int = CELL
) -> list[list[int]]:
    grid = [[0] * cw for _ in range(ch)]
    for item in rects:
        x, y, w, h = int(item[0]), int(item[1]), int(item[2]), int(item[3])
        x0 = max(0, x // cell)
        y0 = max(0, y // cell)
        x1 = min(cw, (x + w + cell - 1) // cell)
        y1 = min(ch, (y + h + cell - 1) // cell)
        for cy in range(y0, y1):
            for cx in range(x0, x1):
                grid[cy][cx] = 1
    return grid


def unexpand_ladder_rect(rect: list) -> list[int] | None:
    x, y, w, h = int(rect[0]), int(rect[1]), int(rect[2]), int(rect[3])
    w2 = w - 8
    if w2 <= 0:
        return None
    return [x + 4, y, w2, h]


def exclusive_ids(solid: list[list[int]], climb: list[list[int]]) -> list[int]:
    """TileMap display: solid wins on hatch lids so floors stay walkable."""
    ch = len(solid)
    cw = len(solid[0]) if ch else 0
    ids: list[int] = []
    for y in range(ch):
        for x in range(cw):
            if solid[y][x]:
                ids.append(SOLID)
            elif climb[y][x]:
                ids.append(LADDER)
            else:
                ids.append(EMPTY)
    return ids


def climb_ids(climb: list[list[int]]) -> list[int]:
    ch = len(climb)
    cw = len(climb[0]) if ch else 0
    return [1 if climb[y][x] else 0 for y in range(ch) for x in range(cw)]


def ids_to_grids(ids: list[int], cw: int, ch: int) -> tuple[list[list[int]], list[list[int]]]:
    solid = [[0] * cw for _ in range(ch)]
    climb = [[0] * cw for _ in range(ch)]
    for i, tid in enumerate(ids):
        x, y = i % cw, i // cw
        if tid == LADDER:
            climb[y][x] = 1
        elif tid == SOLID or tid == ONEWAY:
            solid[y][x] = 1
    return solid, climb


def payload_from_grids(
    solid: list[list[int]],
    climb: list[list[int]],
    *,
    cell: int,
    scale: int,
    size: list[int],
    screen: list[int],
) -> dict:
    ch = len(solid)
    cw = len(solid[0]) if ch else 0
    ids = exclusive_ids(solid, climb)
    return {
        "cell": cell,
        "scale": scale,
        "size": size,
        "screen": screen,
        "grid": [cw, ch],
        "tiles": TILE_NAMES,
        "tileset": "res://assets/tilesets/s2_collision_tileset.tres",
        "atlas_tiles": [4, 1],
        "empty": EMPTY,
        "collision_source": "collision_tiles",
        "note": (
            "rle is exclusive (solid wins on hatch lids) for the TileMap. "
            "ladder_rle is the climb mask including lids. oneway is reserved."
        ),
        "rle": rle_encode(ids),
        "ladder_rle": rle_encode(climb_ids(climb)),
    }


def payload_from_collision_json(data: dict) -> dict:
    cell = int(data.get("cell", CELL))
    size = list(data.get("size", [8192, 4608]))
    cw, ch = size[0] // cell, size[1] // cell
    solid = rasterize_rects(data.get("solids", []), cw, ch, cell)
    climb_rects = []
    for rect in data.get("ladders", []):
        raw = unexpand_ladder_rect(rect)
        if raw:
            climb_rects.append(raw)
    climb = rasterize_rects(climb_rects, cw, ch, cell)
    return payload_from_grids(
        solid,
        climb,
        cell=cell,
        scale=int(data.get("scale", 2)),
        size=size,
        screen=list(data.get("screen", [256, 192])),
    )


def write_collision_tileset() -> Path:
    TILESET_DIR.mkdir(parents=True, exist_ok=True)
    png = TILESET_DIR / "s2_collision_tileset.png"
    im = Image.new("RGBA", (CELL * 4, CELL), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    colors = [
        (40, 40, 40, 90),
        (220, 40, 40, 210),
        (40, 220, 80, 210),
        (220, 200, 40, 210),
    ]
    for i, color in enumerate(colors):
        x0 = i * CELL
        draw.rectangle((x0, 0, x0 + CELL - 1, CELL - 1), fill=color)
        if i == EMPTY:
            continue
        draw.rectangle((x0, 0, x0 + CELL - 1, CELL - 1), outline=(255, 255, 255, 255))
    im.save(png)
    names = ("empty", "solid", "ladder", "oneway")
    lines = [
        '[gd_resource type="TileSet" load_steps=2 format=3]',
        "",
        '[ext_resource type="Texture2D" path="res://assets/tilesets/s2_collision_tileset.png" id="1"]',
        "",
        '[sub_resource type="TileSetAtlasSource" id="TileSetAtlasSource_1"]',
        "texture = ExtResource(\"1\")",
        "texture_region_size = Vector2i(8, 8)",
        "use_texture_padding = true",
    ]
    for i, name in enumerate(names):
        lines.append(f"{i}:0/0 = 0")
        lines.append(f'{i}:0/0/custom_data_0 = "{name}"')
    lines.extend(
        [
            "",
            "[resource]",
            "tile_size = Vector2i(8, 8)",
            'custom_data_layer_0/name = "collision_type"',
            "custom_data_layer_0/type = 4",
            "sources/0 = SubResource(\"TileSetAtlasSource_1\")",
            "",
        ]
    )
    tres = TILESET_DIR / "s2_collision_tileset.tres"
    tres.write_text("\n".join(lines), encoding="utf-8")
    imp = TILESET_DIR / "s2_collision_tileset.png.import"
    if not imp.exists():
        imp.write_text(
            """[remap]

importer="texture"
type="CompressedTexture2D"
uid="uid://s2colltiles8px"
path="res://.godot/imported/s2_collision_tileset.png-s2coll8.ctex"
metadata={
"vram_texture": false
}

[deps]

source_file="res://assets/tilesets/s2_collision_tileset.png"
dest_files=["res://.godot/imported/s2_collision_tileset.png-s2coll8.ctex"]

[params]

compress/mode=0
compress/high_quality=false
compress/lossy_quality=0.7
compress/uastc_level=0
compress/rdo_quality_loss=0.0
compress/hdr_compression=1
compress/normal_map=0
compress/channel_pack=0
mipmaps/generate=false
mipmaps/limit=-1
roughness/mode=0
roughness/src_normal=""
process/channel_remap/red=0
process/channel_remap/green=1
process/channel_remap/blue=2
process/channel_remap/alpha=3
process/fix_alpha_border=false
process/premult_alpha=false
process/normal_map_invert_y=false
process/hdr_as_srgb=false
process/hdr_clamp_exposure=false
process/size_limit=0
detect_3d/compress_to=0
""",
            encoding="utf-8",
        )
    return tres


def crop_screen_rle(runs: list[int], grid: list[int], sx: int, sy: int, sw: int, sh: int) -> list[int]:
    ids = rle_decode(runs)
    cw = int(grid[0])
    out: list[int] = []
    x0, y0 = sx * sw, sy * sh
    for y in range(y0, y0 + sh):
        row = y * cw + x0
        out.extend(ids[row : row + sw])
    return rle_encode(out)


def write_spawn_fixture(tiles: dict, collision: dict, spawn: list[int]) -> Path:
    cell = int(tiles.get("cell", CELL))
    screen = [256, 192]
    sw, sh = screen[0] // cell, screen[1] // cell
    sx = int(spawn[0]) // screen[0]
    sy = int(spawn[1]) // screen[1]
    fixture = {
        "cell": cell,
        "scale": int(tiles.get("scale", 2)),
        "screen": screen,
        "grid": [sw, sh],
        "origin_cell": [sx * sw, sy * sh],
        "spawn_screen": [sx, sy],
        "layers": {},
        "collision": {
            "tiles": TILE_NAMES,
            "empty": EMPTY,
            "rle": crop_screen_rle(
                collision["rle"], collision["grid"], sx, sy, sw, sh
            ),
            "ladder_rle": crop_screen_rle(
                collision.get("ladder_rle", []), collision["grid"], sx, sy, sw, sh
            ),
        },
    }
    for name, spec in tiles.get("layers", {}).items():
        fixture["layers"][name] = {
            "tileset": spec.get("tileset"),
            "atlas_tiles": spec.get("atlas_tiles"),
            "empty": spec.get("empty"),
            "z": spec.get("z"),
            "rle": crop_screen_rle(spec["rle"], tiles["grid"], sx, sy, sw, sh),
        }
    path = ROOT / "test" / "fixtures" / "screen_spawn_tiles.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(fixture, separators=(",", ":")), encoding="utf-8")
    return path


def pack_tile_map_bytes(ids: list[int], atlas_cols: int, empty_id: int, cw: int) -> bytes:
    out = bytearray()
    out += (0).to_bytes(2, "little", signed=False)
    for i, tid in enumerate(ids):
        if tid == empty_id:
            continue
        x, y = i % cw, i // cw
        ax, ay = tid % atlas_cols, tid // atlas_cols
        out += int(x).to_bytes(2, "little", signed=True)
        out += int(y).to_bytes(2, "little", signed=True)
        out += int(0).to_bytes(2, "little", signed=False)
        out += int(ax).to_bytes(2, "little", signed=False)
        out += int(ay).to_bytes(2, "little", signed=False)
        out += int(0).to_bytes(2, "little", signed=False)
    return bytes(out)


def packed_to_godot(data: bytes) -> str:
    return ", ".join(str(b) for b in data)


def write_spawn_scene(fixture: dict) -> Path:
    """Bake one Spectrum screen so Godot can open an editable map fragment."""
    sw, sh = fixture["grid"]
    scale = int(fixture.get("scale", 2))
    ox, oy = fixture["origin_cell"]
    resources = [
        '[gd_scene load_steps=8 format=3 uid="uid://s2spawnscreen"]',
        "",
    ]
    ext = []
    nodes = [
        '[node name="SpawnScreen" type="Node2D"]',
        "",
    ]
    rid = 1
    layer_nodes = [
        ("sky", "Sky"),
        ("earth", "Earth"),
        ("structure", "Structure"),
        ("wallpaper", "Wallpaper"),
        ("interior", "Interior"),
        ("fg", "Foreground"),
    ]
    for key, node_name in layer_nodes:
        spec = fixture["layers"][key]
        ext.append(
            f'[ext_resource type="TileSet" path="{spec["tileset"]}" id="{rid}"]'
        )
        ids = rle_decode(spec["rle"])
        cols = int(spec["atlas_tiles"][0])
        empty = spec.get("empty")
        packed = pack_tile_map_bytes(ids, cols, empty if empty is not None else -1, sw)
        z = int(spec.get("z", 0))
        nodes.append(f'[node name="{node_name}" type="TileMapLayer" parent="."]')
        nodes.append(f"z_index = {z}")
        nodes.append(f"scale = Vector2({scale}, {scale})")
        nodes.append(f"tile_set = ExtResource(\"{rid}\")")
        if packed:
            nodes.append(f"tile_map_data = PackedByteArray({packed_to_godot(packed)})")
        nodes.append("")
        rid += 1
    ext.append(
        '[ext_resource type="TileSet" path="res://assets/tilesets/s2_collision_tileset.tres" id="7"]'
    )
    cids = rle_decode(fixture["collision"]["rle"])
    cpacked = pack_tile_map_bytes(cids, 4, EMPTY, sw)
    nodes.append('[node name="CollisionLayer" type="TileMapLayer" parent="."]')
    nodes.append("visible = false")
    nodes.append("z_index = 20")
    nodes.append(f"scale = Vector2({scale}, {scale})")
    nodes.append('tile_set = ExtResource("7")')
    if cpacked:
        nodes.append(f"tile_map_data = PackedByteArray({packed_to_godot(cpacked)})")
    nodes.append("")
    path = ROOT / "scenes" / "levels" / "screen_spawn.tscn"
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(resources + ext + [""] + nodes)
    path.write_text(text, encoding="utf-8")
    _ = (ox, oy, sh)
    return path


def export_from_collision_json(
    collision_path: Path | None = None, tiles_path: Path | None = None
) -> dict:
    collision_path = collision_path or (OUT / "s2_collision.json")
    tiles_path = tiles_path or (OUT / "s2_world_tiles.json")
    data = json.loads(collision_path.read_text(encoding="utf-8"))
    payload = payload_from_collision_json(data)
    out = OUT / "s2_collision_tiles.json"
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    write_collision_tileset()
    tiles = json.loads(tiles_path.read_text(encoding="utf-8"))
    entities = json.loads((OUT / "s2_entities.json").read_text(encoding="utf-8"))
    spawn = list(entities.get("spawn", [2240, 600]))
    fixture_path = write_spawn_fixture(tiles, payload, spawn)
    fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
    scene = write_spawn_scene(fixture)
    used = sum(1 for t in rle_decode(payload["rle"]) if t != EMPTY)
    print(
        f"wrote {out} used={used} solids_rects={len(data.get('solids', []))} "
        f"ladders={len(data.get('ladders', []))} fixture={fixture_path} scene={scene}"
    )
    return payload


def export_from_stamp_grids(
    solid: list[list[int]],
    climb: list[list[int]],
    *,
    cell: int,
    scale: int,
    size: list[int],
    screen: list[int],
) -> dict:
    payload = payload_from_grids(
        solid, climb, cell=cell, scale=scale, size=size, screen=screen
    )
    out = OUT / "s2_collision_tiles.json"
    out.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    write_collision_tileset()
    return payload


def main() -> None:
    export_from_collision_json()


if __name__ == "__main__":
    sys.exit(main() or 0)
