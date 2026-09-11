"""World layer ids, visual assignment, atlas export and object catalog.

Authoring layers (z-order for TileMapLayer):
  0 sky, 1 earth, 2 structure, 3 wallpaper, 4 interior, 8 fg.
Layers 5–7 (machines, artifacts, actors) are runtime nodes, not tile grids.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from PIL import Image

CELL = 8

SKY = 0
EARTH = 1
STRUCTURE = 2
WALLPAPER = 3
INTERIOR = 4
MACHINES = 5
ARTIFACTS = 6
ACTORS = 7
FG = 8

TILE_LAYER_IDS = (SKY, EARTH, STRUCTURE, WALLPAPER, INTERIOR, FG)

LAYER_NAMES: dict[int, str] = {
    SKY: "sky",
    EARTH: "earth",
    STRUCTURE: "structure",
    WALLPAPER: "wallpaper",
    INTERIOR: "interior",
    MACHINES: "machines",
    ARTIFACTS: "artifacts",
    ACTORS: "actors",
    FG: "fg",
}

LAYER_Z: dict[int, int] = {
    SKY: -30,
    EARTH: -20,
    STRUCTURE: -10,
    WALLPAPER: -5,
    INTERIOR: 0,
    FG: 12,
}

# Gameplay collision from the visual object role. "solid"/"floor"/"ceiling"
# become the walk/block mask; "climb" is a ladder zone; "none" is air.
ROLE_COLLISION: dict[str, str] = {
    "brick_red": "solid",
    "floor_diamond": "floor",
    "speckled": "solid",
    "solid": "solid",
    "floor": "floor",
    "ceiling": "solid",
    "climb": "climb",
    "ladder_green": "climb",
    "ladder_sky": "climb",
    "ladder_lattice": "climb",
    "paper": "none",
    "wall": "none",
    "sky": "none",
    "decor": "none",
    "crate": "none",
    "bookcase": "none",
    "item_chrome": "none",
    "none": "none",
    "": "none",
}

# Legacy role → collision map (visual layers). Gameplay collision is stamped
# from object_types.py; these roles are for sprite catalog metadata only.
INITIAL_SOLID_ROLES = frozenset(
    role for role, kind in ROLE_COLLISION.items() if kind == "solid"
)
FLOOR_ROLES = frozenset(
    role for role, kind in ROLE_COLLISION.items() if kind == "floor"
)
CLIMB_ROLES = frozenset(
    role for role, kind in ROLE_COLLISION.items() if kind == "climb"
)


def collision_for_role(role: str) -> str:
    return ROLE_COLLISION.get(role, "none")


def collision_masks_from_roles(
    roles: list[list[str]],
) -> tuple[list[list[int]], list[list[int]]]:
    """solid / raw-ladder grids from object roles. No pixel heuristics."""
    ch = len(roles)
    cw = len(roles[0]) if ch else 0
    solid = [[0] * cw for _ in range(ch)]
    ladder = [[0] * cw for _ in range(ch)]
    for cy in range(ch):
        for cx in range(cw):
            kind = collision_for_role(roles[cy][cx])
            if kind == "solid":
                solid[cy][cx] = 1
            elif kind == "climb":
                ladder[cy][cx] = 1
    return solid, _filter_thin_ladders(ladder)


def stamp_floor_roles(solid: list[list[int]], roles: list[list[str]]) -> int:
    """Add one-cell floors after thicken so they never grow downward."""
    ch = len(roles)
    cw = len(roles[0]) if ch else 0
    added = 0
    for cy in range(ch):
        for cx in range(cw):
            if collision_for_role(roles[cy][cx]) != "floor":
                continue
            if not solid[cy][cx]:
                solid[cy][cx] = 1
                added += 1
    return added


def _filter_thin_ladders(ladder: list[list[int]]) -> list[list[int]]:
    """Keep only vertical runs of 3+ cells that are at most two tiles wide."""
    ch = len(ladder)
    cw = len(ladder[0]) if ch else 0
    keep = [[0] * cw for _ in range(ch)]
    for cx in range(cw):
        cy = 0
        while cy < ch:
            if not ladder[cy][cx]:
                cy += 1
                continue
            y0 = cy
            while cy < ch and ladder[cy][cx]:
                cy += 1
            if cy - y0 < 3:
                continue
            for y in range(y0, cy):
                wide = 0
                for dx in (-1, 0, 1):
                    xx = cx + dx
                    if 0 <= xx < cw and ladder[y][xx]:
                        wide += 1
                if wide <= 2:
                    keep[y][cx] = 1
    return keep


# Known tile aliases (layer_name, hash prefix) -> stable id for artists.
KNOWN_ALIASES: dict[tuple[str, str], str] = {
    ("fg", "crate"): "crate",
    ("fg", "item_chrome"): "item_chrome",
    ("interior", "ladder_green"): "ladder_green",
    ("interior", "ladder_sky"): "ladder_sky",
    ("interior", "ladder_lattice"): "ladder_lattice",
    ("structure", "floor_diamond"): "floor_diamond",
    ("structure", "brick_red"): "brick_red",
    ("earth", "speckled"): "earth_speckled",
    ("wallpaper", "cave_paper"): "paper_blue_brick",
    ("wallpaper", "green"): "paper_green",
    ("sky", "open"): "sky_open",
}


def assign_visual_layers(
    px,
    fg: list[list[int]],
    bookcase: list[list[int]],
    biomes: list[str],
    sx_n: int,
    *,
    cell_is_ladder,
    cell_is_crate,
    cell_is_item_chrome,
    cell_is_red_brick,
    cell_is_diamond_floor,
    cell_counts,
    is_cave_paper,
    is_speckled_earth,
    is_open_sky,
    is_cracked_earth,
    biome_at,
    opens_onto_night_sky,
) -> tuple[list[list[int]], list[list[str]]]:
    """Per-cell authoring layer and gameplay role from the mosaic.

    Collision is *not* decided here — ROLE_COLLISION maps role → solid/climb/none.
    """
    ch = len(fg)
    cw = len(fg[0])
    layers = [[-1] * cw for _ in range(ch)]
    roles = [[""] * cw for _ in range(ch)]

    for cy in range(ch):
        for cx in range(cw):
            counts = cell_counts(px, cx, cy)
            biome = biome_at(biomes, sx_n, cx, cy)

            if fg[cy][cx]:
                layers[cy][cx] = FG
                if cell_is_ladder(px, cx, cy):
                    roles[cy][cx] = "climb"
                elif cell_is_crate(counts):
                    roles[cy][cx] = "crate"
                elif bookcase[cy][cx]:
                    roles[cy][cx] = "bookcase"
                elif cell_is_item_chrome(counts):
                    roles[cy][cx] = "item_chrome"
                else:
                    roles[cy][cx] = "decor"
                continue

            if cell_is_ladder(px, cx, cy):
                layers[cy][cx] = INTERIOR
                roles[cy][cx] = "climb"
                continue

            if is_cave_paper(counts):
                layers[cy][cx] = WALLPAPER
                roles[cy][cx] = "paper"
                continue

            if cell_is_diamond_floor(px, cx, cy):
                layers[cy][cx] = STRUCTURE
                roles[cy][cx] = "floor_diamond"
                continue

            red_brick = cell_is_red_brick(counts)
            speckled_earth = is_speckled_earth(counts)
            cracked = is_cracked_earth(counts)
            black_wall = counts["k"] >= 40 and counts["g"] < 20

            if biome == "sky":
                if red_brick:
                    layers[cy][cx] = STRUCTURE
                    roles[cy][cx] = "brick_red"
                elif is_open_sky(counts) or counts["b"] >= 40:
                    layers[cy][cx] = SKY
                    roles[cy][cx] = "sky"
                continue

            if biome == "interior":
                if red_brick:
                    layers[cy][cx] = STRUCTURE
                    roles[cy][cx] = "brick_red"
                elif speckled_earth or cracked:
                    if not opens_onto_night_sky(px, cx, cy, cw):
                        layers[cy][cx] = EARTH
                        roles[cy][cx] = "speckled"
                    else:
                        layers[cy][cx] = SKY
                        roles[cy][cx] = "sky"
                elif black_wall and (cx < 3 or cx >= cw - 3 or cy >= ch - 3):
                    layers[cy][cx] = STRUCTURE
                    roles[cy][cx] = "solid"
                elif counts["g"] >= 16 and counts["k"] < 30:
                    layers[cy][cx] = WALLPAPER
                    roles[cy][cx] = "wall"
                continue

            # cave
            if red_brick:
                layers[cy][cx] = STRUCTURE
                roles[cy][cx] = "brick_red"
            elif speckled_earth or cracked:
                layers[cy][cx] = EARTH
                roles[cy][cx] = "speckled"
            elif counts["g"] >= 16 and counts["k"] < 30:
                layers[cy][cx] = WALLPAPER
                roles[cy][cx] = "wall"
            elif counts["b"] >= 20 and counts["k"] >= 6:
                layers[cy][cx] = WALLPAPER
                roles[cy][cx] = "paper"

    return layers, roles


def build_layer_images(
    world_rgb: Image.Image,
    fg_rgba: Image.Image,
    layer_grid: list[list[int]],
    bookcase: list[list[int]],
) -> dict[int, Image.Image]:
    """Raster images per tile layer. Empty cells stay black (RGB) or transparent (RGBA)."""
    w, h = world_rgb.size
    cw, ch = w // CELL, h // CELL
    wp = world_rgb.load()
    fp = fg_rgba.load()
    out: dict[int, Image.Image] = {}
    for lid in TILE_LAYER_IDS:
        if lid == FG:
            out[lid] = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        else:
            out[lid] = Image.new("RGB", (w, h), (0, 0, 0))

    for cy in range(ch):
        for cx in range(cw):
            lid = layer_grid[cy][cx]
            if lid < 0:
                continue
            x0, y0 = cx * CELL, cy * CELL
            if lid == FG:
                op = out[FG].load()
                for y in range(y0, y0 + CELL):
                    for x in range(x0, x0 + CELL):
                        op[x, y] = fp[x, y]
                continue
            op = out[lid].load()
            for y in range(y0, y0 + CELL):
                for x in range(x0, x0 + CELL):
                    if bookcase[cy][cx] and lid != FG:
                        op[x, y] = (0, 0, 0)
                    else:
                        op[x, y] = wp[x, y][:3]
    return out


def composite_world_layers(images: dict[int, Image.Image]) -> Image.Image:
    """Bottom-up RGB composite of layers 0–4 (later over earlier)."""
    base = next(iter(images.values()))
    w, h = base.size
    out = Image.new("RGB", (w, h), (0, 0, 0))
    for lid in (SKY, EARTH, STRUCTURE, WALLPAPER, INTERIOR):
        src = images.get(lid)
        if src is None:
            continue
        sp = src.load()
        op = out.load()
        for y in range(h):
            for x in range(w):
                r, g, b = sp[x, y]
                if r or g or b:
                    op[x, y] = (r, g, b)
    return out


def _tile_hash(tile: Image.Image) -> str:
    return hashlib.sha256(tile.tobytes()).hexdigest()[:12]


def _alias_for(layer_name: str, role: str, tile: Image.Image) -> str | None:
    if role and (layer_name, role) in KNOWN_ALIASES:
        return KNOWN_ALIASES[(layer_name, role)]
    key = (layer_name, _tile_hash(tile)[:6])
    return KNOWN_ALIASES.get(key)


def _safe_id(name: str) -> str:
    return re.sub(r"[^a-z0-9_]+", "_", name.lower()).strip("_") or "tile"


def export_object_catalog(
    layer_images: dict[int, Image.Image],
    layer_grid: list[list[int]],
    role_grid: list[list[str]],
    objects_dir: Path,
    type_grid: list[list[str]] | None = None,
    type_defs: dict[str, dict] | None = None,
) -> dict:
    """Write PNG sprites + s2_objects.json (defs + interior/fg placements)."""
    objects_dir.mkdir(parents=True, exist_ok=True)
    defs: dict[str, dict] = {}
    hash_to_id: dict[tuple[str, str], str] = {}
    placements: list[dict] = []
    ch = len(layer_grid)
    cw = len(layer_grid[0])

    for lid in TILE_LAYER_IDS:
        lname = LAYER_NAMES[lid]
        sub = objects_dir / lname
        sub.mkdir(parents=True, exist_ok=True)
        img = layer_images[lid]
        for cy in range(ch):
            for cx in range(cw):
                if layer_grid[cy][cx] != lid:
                    continue
                tile = img.crop((cx * CELL, cy * CELL, cx * CELL + CELL, cy * CELL + CELL))
                if lid == FG and _is_fully_transparent(tile):
                    continue
                if lid != FG and max(tile.getextrema()[0]) == 0 and max(tile.getextrema()[1]) == 0:
                    if max(tile.getextrema()[2]) == 0:
                        continue
                role = role_grid[cy][cx]
                obj_type = type_grid[cy][cx] if type_grid else ""
                th = _tile_hash(tile)
                key = (lname, th)
                oid = hash_to_id.get(key)
                if oid is None:
                    alias = _alias_for(lname, role, tile)
                    oid = alias if alias else f"t_{th[:8]}"
                    if oid in defs:
                        oid = f"t_{th[:8]}"
                    hash_to_id[key] = oid
                    rel = f"res://assets/world/objects/{lname}/{oid}.png"
                    tile.save(objects_dir / lname / f"{oid}.png")
                    entry: dict = {
                        "layer": lname,
                        "role": role or "none",
                        "collision": collision_for_role(role),
                        "size_cells": [1, 1],
                        "sprite": rel,
                    }
                    if obj_type:
                        entry["type"] = obj_type
                    defs[oid] = entry
                if lid in (INTERIOR, FG):
                    placements.append({"id": oid, "x": cx, "y": cy, **({"type": obj_type} if obj_type else {})})

    out: dict = {
        "cell": CELL,
        "defs": defs,
        "placements": placements,
        "collision": ROLE_COLLISION,
        "layer_z": {LAYER_NAMES[k]: v for k, v in LAYER_Z.items() if k in TILE_LAYER_IDS},
    }
    if type_defs:
        out["types"] = type_defs
    return out


def _is_fully_transparent(tile: Image.Image) -> bool:
    if tile.mode != "RGBA":
        return False
    extrema = tile.getextrema()
    return extrema is not None and extrema[3] == (0, 0)


def export_layer_tilesets(
    layer_images: dict[int, Image.Image],
    tileset_dir: Path,
    out_dir: Path,
    scale: int,
    size: tuple[int, int],
    *,
    collect_unique_cells,
    pack_atlas,
    reconstruct_from_atlas,
    rle_encode,
    write_tileset_tres,
    layer_texture_uids: dict[str, str],
) -> dict:
    """Atlases + RLE per tile layer; returns payload for s2_world_tiles.json."""
    tileset_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    cw, ch = size[0] // CELL, size[1] // CELL
    payload: dict = {
        "cell": CELL,
        "scale": scale,
        "size": list(size),
        "grid": [cw, ch],
        "note": "Per-layer visual tiles. Collision in s2_collision.json.",
        "layers": {},
    }
    legacy_world: dict | None = None
    legacy_fg: dict | None = None

    for lid in TILE_LAYER_IDS:
        name = LAYER_NAMES[lid]
        mode = "RGBA" if lid == FG else "RGB"
        im = layer_images[lid]
        tiles, ids, _, _, empty_id = collect_unique_cells(im, mode)
        atlas, atlas_cols, atlas_rows = pack_atlas(tiles)
        atlas_name = f"s2_{name}_tileset.png"
        tres_name = f"s2_{name}_tileset.tres"
        atlas_path = tileset_dir / atlas_name
        atlas.save(atlas_path)
        saved = Image.open(atlas_path).convert(mode)
        rebuilt = reconstruct_from_atlas(saved, ids, cw, ch, atlas_cols, mode)
        if rebuilt.tobytes() != im.convert(mode).tobytes():
            raise RuntimeError(f"{name} layer atlas is not pixel-identical to source")
        rle = rle_encode(ids)
        texture_res = f"res://assets/tilesets/{atlas_name}"
        uid = layer_texture_uids.get(name, f"uid://s2layer{name}")
        write_tileset_tres(
            tileset_dir / tres_name,
            texture_res,
            uid,
            atlas_cols,
            atlas_rows,
            len(tiles),
        )
        layer_payload = {
            "id": lid,
            "z": LAYER_Z[lid],
            "atlas": texture_res,
            "tileset": f"res://assets/tilesets/{tres_name}",
            "atlas_tiles": [atlas_cols, atlas_rows],
            "tile_count": len(tiles),
            "empty": empty_id,
            "rle": rle,
        }
        payload["layers"][name] = layer_payload
        if name == "sky":
            # Legacy `world` = composite 0–4 for old loaders.
            pass
        print(f"layer {name}: unique {len(tiles)} atlas {atlas.size}")

    # Legacy world = composite layers 0-4 encoded as one RGB atlas.
    composite = composite_world_layers(layer_images)
    world_tiles, world_ids, _, _, _ = collect_unique_cells(composite, "RGB")
    world_atlas, wcols, wrows = pack_atlas(world_tiles)
    world_atlas.save(tileset_dir / "s2_world_tileset.png")
    legacy_world = {
        "atlas": "res://assets/tilesets/s2_world_tileset.png",
        "tileset": "res://assets/tilesets/s2_world_tileset.tres",
        "atlas_tiles": [wcols, wrows],
        "tile_count": len(world_tiles),
        "empty": None,
        "rle": rle_encode(world_ids),
    }
    write_tileset_tres(
        tileset_dir / "s2_world_tileset.tres",
        "res://assets/tilesets/s2_world_tileset.png",
        layer_texture_uids.get("world", "uid://dma7fdoakrrr6"),
        wcols,
        wrows,
        len(world_tiles),
    )
    payload["world"] = legacy_world
    payload["fg"] = payload["layers"]["fg"]
    return payload


def write_objects_json(catalog: dict, path: Path) -> None:
    path.write_text(json.dumps(catalog, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {path} ({path.stat().st_size} bytes, {len(catalog['defs'])} defs)")
