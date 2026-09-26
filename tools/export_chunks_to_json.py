#!/usr/bin/env python3
"""Export Saboteur-92 world chunk .tscn scenes to the intermediate JSON schema.

This is the *Godot -> JSON* half of the two-way bridge (see WorldBuilder.gd for
the reverse). It is deliberately dependency-free (std-lib only) and parses the
text `.tscn` / `.tres` formats directly.

.tscn parsing assumptions (verified against scenes/world/chunks/*.tscn):
  * A chunk is a `Node2D` root with several `TileMapLayer` children:
        Earth, Structure, Wallpaper, Mosaic, Interior1, Interior2,
        StructureFront, Foreground, CollisionLayer
    Each layer references its own TileSet via `tile_set = ExtResource("<id>")`.
  * Tiles are stored in the Godot 4.3+ TileMapLayer binary property
        tile_map_data = PackedByteArray("<base64>")
    Layout (little-endian):
        bytes[0:2]   uint16 format header (currently 0)
        then repeated 12-byte cells:
            int16  x            (chunk-local cell x)
            int16  y            (chunk-local cell y)
            uint16 source_id    (always 0 in this project)
            uint16 atlas_x
            uint16 atlas_y
            uint16 alternative_tile
    Older/empty chunks simply omit the property.
  * Because that binary is trivial to decode in pure Python, NO GDScript helper
    is required. (If a future Godot format changes this, dump cells from the
    editor with a tool script:
        for c in layer.get_used_cells():
            print(c, layer.get_cell_source_id(c),
                  layer.get_cell_atlas_coords(c),
                  layer.get_cell_alternative_tile(c))
    and feed that instead.)

Tile identity is (source_id, atlas_x, atlas_y, alternative). This exporter
assigns each *distinct* tile a small sequential PALETTE id (0..N) per TileSet,
writing the lookup table to tile_id_map.json so WorldBuilder.gd can map ids
back to atlas coordinates. The mapping is data-driven, never hardcoded.

Usage:
    python tools/export_chunks_to_json.py \
        --chunks-dir scenes/world/chunks \
        --tilesets-dir assets/tilesets \
        --out-dir assets/world/chunks_json \
        --map-out assets/tilesets/tile_id_map.json \
        [--encoding grid|rle] \
        [--entities assets/world/s2_entities.json]
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import struct
import sys
from dataclasses import dataclass, field
from typing import Optional

# --- Constants tied to the project ------------------------------------------

CELL_SIZE = 8
GRID_W = 128
GRID_H = 72
EMPTY_ID = -1

# Godot node name -> layer key (snake_case) used in the JSON schema.
NODE_TO_KEY = {
    "Earth": "earth",
    "Structure": "structure",
    "Wallpaper": "wallpaper",
    "Mosaic": "mosaic",
    "Interior1": "interior1",
    "Interior2": "interior2",
    "StructureFront": "structure_front",
    "Foreground": "foreground",
    "CollisionLayer": "collision",
}

# Coarse role used by the loader / validator. terrain = blocks movement source;
# collision = the authoritative walkability layer; others are purely visual.
LAYER_ROLE = {
    "earth": "terrain",
    "structure": "terrain",
    "wallpaper": "background",
    "mosaic": "background",
    "interior1": "interior",
    "interior2": "interior",
    "structure_front": "terrain",
    "foreground": "foreground",
    "collision": "collision",
}

# Default logical-type -> prefab map seeded into tile_id_map.json. Edit freely;
# the exporter only *seeds* missing keys, it never overwrites your edits.
DEFAULT_ENTITY_PREFABS = {
    "spawn": "",
    "guard": "res://scenes/enemies/guard.tscn",
    "key_item": "res://scenes/items/pickup.tscn",
    "document": "res://scenes/items/pickup.tscn",
    "bomb": "res://scenes/items/pickup.tscn",
    "sabotage_target": "res://scenes/items/sabotage_target.tscn",
    "exit": "res://scenes/items/exit_zone.tscn",
}


# --- .tscn / .tres parsing ---------------------------------------------------

@dataclass
class TscnNode:
    name: str
    type: str
    parent: Optional[str]
    body: str


def _split_sections(text: str) -> list[str]:
    """Split a .tscn/.tres into `[header]...` sections, keeping the header."""
    parts = re.split(r"(?m)^(?=\[)", text)
    return [p for p in parts if p.strip()]


def parse_ext_resources(text: str) -> dict[str, str]:
    """id -> res:// path for every [ext_resource ...] line."""
    out: dict[str, str] = {}
    for m in re.finditer(r'\[ext_resource\b[^\]]*\]', text):
        line = m.group(0)
        # `(?<![A-Za-z])` so we match the real `id="..."` and NOT the `id="`
        # substring inside `uid="uid://..."` (newer chunks carry both).
        rid = re.search(r'(?<![A-Za-z])id="([^"]+)"', line)
        path = re.search(r'path="([^"]+)"', line)
        if rid and path:
            out[rid.group(1)] = path.group(1)
    return out


def parse_nodes(text: str) -> list[TscnNode]:
    nodes: list[TscnNode] = []
    for sec in _split_sections(text):
        if not sec.lstrip().startswith("[node "):
            continue
        header, _, body = sec.partition("]")
        name = re.search(r'name="([^"]+)"', header)
        ntype = re.search(r'type="([^"]+)"', header)
        parent = re.search(r'parent="([^"]+)"', header)
        nodes.append(
            TscnNode(
                name=name.group(1) if name else "",
                type=ntype.group(1) if ntype else "",
                parent=parent.group(1) if parent else None,
                body=body,
            )
        )
    return nodes


def decode_tile_map_data(b64: str) -> list[tuple[int, int, int, int, int, int]]:
    """Decode a PackedByteArray tile_map_data blob into (x,y,src,ax,ay,alt)."""
    raw = base64.b64decode(b64)
    cells: list[tuple[int, int, int, int, int, int]] = []
    if len(raw) < 2:
        return cells
    # raw[0:2] is the format header; we don't need its value to read v0 data.
    off = 2
    while off + 12 <= len(raw):
        x, y, src, ax, ay, alt = struct.unpack_from("<hhHHHH", raw, off)
        cells.append((x, y, src, ax, ay, alt))
        off += 12
    return cells


def extract_layer(node: TscnNode) -> dict:
    """Pull tile cells + presentation props from a TileMapLayer node body."""
    dm = re.search(r'tile_map_data\s*=\s*PackedByteArray\("([^"]*)"\)', node.body)
    cells = decode_tile_map_data(dm.group(1)) if dm else []
    ts = re.search(r'tile_set\s*=\s*ExtResource\("([^"]+)"\)', node.body)
    z = re.search(r'z_index\s*=\s*(-?\d+)', node.body)
    vis = re.search(r'visible\s*=\s*(true|false)', node.body)
    return {
        "cells": cells,
        "tileset_ext_id": ts.group(1) if ts else None,
        "z_index": int(z.group(1)) if z else 0,
        "visible": (vis.group(1) == "true") if vis else True,
    }


def parse_tileset_custom_data(tres_path: str) -> dict[tuple[int, int, int], str]:
    """For the collision tileset: (atlas_x, atlas_y, alt) -> collision_type str.

    Reads lines like `1:0/0/custom_data_0 = "solid"`. custom_data_0 is the
    first custom-data layer (named 'collision_type' in this project).
    """
    out: dict[tuple[int, int, int], str] = {}
    if not os.path.isfile(tres_path):
        return out
    with open(tres_path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(
                r'\s*(\d+):(\d+)/(\d+)/custom_data_0\s*=\s*"([^"]*)"', line
            )
            if m:
                ax, ay, alt, val = m.groups()
                out[(int(ax), int(ay), int(alt))] = val
    return out


def parse_tileset_tile_size(tres_path: str) -> list[int]:
    if not os.path.isfile(tres_path):
        return [CELL_SIZE, CELL_SIZE]
    txt = open(tres_path, encoding="utf-8").read()
    m = re.search(r'tile_size\s*=\s*Vector2i\((\d+),\s*(\d+)\)', txt)
    if m:
        return [int(m.group(1)), int(m.group(2))]
    m = re.search(r'texture_region_size\s*=\s*Vector2i\((\d+),\s*(\d+)\)', txt)
    return [int(m.group(1)), int(m.group(2))] if m else [CELL_SIZE, CELL_SIZE]


# --- Palette accumulation (distinct tiles -> sequential ids) ----------------

@dataclass
class Palette:
    """Per-TileSet lookup: distinct (src,ax,ay,alt) tuples -> palette id."""

    tileset_path: str
    tile_size: list[int]
    tiles: list[tuple[int, int, int, int]] = field(default_factory=list)
    _index: dict[tuple[int, int, int, int], int] = field(default_factory=dict)
    collision_types: list[str] = field(default_factory=list)
    is_collision: bool = False
    _custom: dict[tuple[int, int, int], str] = field(default_factory=dict)

    def id_for(self, tile: tuple[int, int, int, int]) -> int:
        if tile not in self._index:
            self._index[tile] = len(self.tiles)
            self.tiles.append(tile)
            if self.is_collision:
                src, ax, ay, alt = tile
                self.collision_types.append(
                    self._custom.get((ax, ay, alt), "empty")
                )
        return self._index[tile]

    def to_json(self) -> dict:
        out = {
            "tileset": self.tileset_path,
            "tile_size": self.tile_size,
            "tiles": [list(t) for t in self.tiles],
        }
        if self.is_collision:
            out["collision_types"] = self.collision_types
        return out


def palette_key(tileset_path: str) -> str:
    """Stable palette key = tileset file stem, e.g. 's2_earth_tileset'."""
    return os.path.splitext(os.path.basename(tileset_path))[0]


# --- Grid encoding -----------------------------------------------------------

def cells_to_grid(cells, palette: Palette, w: int, h: int) -> list[list[int]]:
    grid = [[EMPTY_ID] * w for _ in range(h)]
    for (x, y, src, ax, ay, alt) in cells:
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = palette.id_for((src, ax, ay, alt))
    return grid


def grid_to_rle(grid: list[list[int]]) -> list[int]:
    flat: list[int] = []
    for row in grid:
        flat.extend(row)
    out: list[int] = []
    if not flat:
        return out
    prev, count = flat[0], 1
    for v in flat[1:]:
        if v == prev:
            count += 1
        else:
            out.extend((prev, count))
            prev, count = v, 1
    out.extend((prev, count))
    return out


# --- Entity extraction -------------------------------------------------------

def extract_entities_from_nodes(nodes: list[TscnNode]) -> list[dict]:
    """Generic: any non-root, non-TileMapLayer node becomes an entity.

    Current chunks have none, but this future-proofs the exporter for when
    guards/items are authored directly inside chunk scenes. Position is read
    from `position = Vector2(x, y)` (native px) and converted to cells.
    """
    entities: list[dict] = []
    for n in nodes:
        if n.parent is None or n.type in ("Node2D", "TileMapLayer", ""):
            continue
        pm = re.search(r'position\s*=\s*Vector2\(([-\d.]+),\s*([-\d.]+)\)', n.body)
        px = float(pm.group(1)) if pm else 0.0
        py = float(pm.group(2)) if pm else 0.0
        entities.append(
            {
                "type": n.name.lower(),
                "id": n.name,
                "position": [round(px / CELL_SIZE, 3), round(py / CELL_SIZE, 3)],
                "params": {"godot_type": n.type},
            }
        )
    return entities


def bin_world_entities(entities_path: str, chunk_col: int, chunk_row: int) -> list[dict]:
    """Optional: slice a whole-world s2_entities.json into this chunk.

    s2_entities.json stores positions in whole-world *native* pixels. A tile is
    in chunk (col,row) if its px falls inside [col*W*cell, (col+1)*W*cell). We
    convert to chunk-local CELL coordinates for the schema.
    """
    if not entities_path or not os.path.isfile(entities_path):
        return []
    data = json.load(open(entities_path, encoding="utf-8"))
    chunk_px_w = GRID_W * CELL_SIZE
    chunk_px_h = GRID_H * CELL_SIZE
    x0 = chunk_col * chunk_px_w
    y0 = chunk_row * chunk_px_h
    out: list[dict] = []

    def emit(etype: str, x: float, y: float, params: dict, eid: str = "") -> None:
        if not (x0 <= x < x0 + chunk_px_w and y0 <= y < y0 + chunk_px_h):
            return
        rec = {
            "type": etype,
            "position": [round((x - x0) / CELL_SIZE, 3), round((y - y0) / CELL_SIZE, 3)],
            "params": params,
        }
        if eid:
            rec["id"] = eid
        out.append(rec)

    sp = data.get("spawn")
    if isinstance(sp, list) and len(sp) >= 2:
        emit("spawn", float(sp[0]), float(sp[1]), {})
    for it in data.get("items", []):
        emit(it.get("type", "key_item"), float(it["x"]), float(it["y"]),
             {"required": it.get("required", "")}, it.get("id", ""))
    for g in data.get("guards", []):
        emit("guard", float(g["x"]), float(g["y"]),
             {"patrol": g.get("patrol", 40)}, g.get("id", ""))
    for key, etype in (("sabotage", "sabotage_target"), ("exit", "exit")):
        obj = data.get(key)
        if isinstance(obj, dict) and "x" in obj:
            emit(etype, float(obj["x"]), float(obj["y"]), {})
    return out


# --- Main export -------------------------------------------------------------

def chunk_col_row(chunk_id: str) -> tuple[int, int]:
    m = re.search(r'(\d+)_(\d+)$', chunk_id)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def export(args: argparse.Namespace) -> int:
    chunk_files = sorted(
        f for f in os.listdir(args.chunks_dir) if f.endswith(".tscn")
    )
    if not chunk_files:
        print(f"No .tscn files in {args.chunks_dir}", file=sys.stderr)
        return 1

    os.makedirs(args.out_dir, exist_ok=True)
    palettes: dict[str, Palette] = {}
    layers_config: dict[str, dict] = {}
    layer_order: list[str] = []
    exported: list[dict] = []

    for fname in chunk_files:
        path = os.path.join(args.chunks_dir, fname)
        text = open(path, encoding="utf-8").read()
        ext = parse_ext_resources(text)
        nodes = parse_nodes(text)
        chunk_id = os.path.splitext(fname)[0]
        col, row = chunk_col_row(chunk_id)

        chunk_layers: dict[str, dict] = {}
        for n in nodes:
            if n.type != "TileMapLayer":
                continue
            key = NODE_TO_KEY.get(n.name)
            if key is None:
                continue
            info = extract_layer(n)
            ts_path = ext.get(info["tileset_ext_id"], "")
            pkey = palette_key(ts_path) if ts_path else key
            if pkey not in palettes:
                is_col = key == "collision"
                pal = Palette(
                    tileset_path=ts_path,
                    tile_size=parse_tileset_tile_size(
                        _res_to_fs(ts_path, args.project_root)
                    ),
                    is_collision=is_col,
                )
                if is_col:
                    pal._custom = parse_tileset_custom_data(
                        _res_to_fs(ts_path, args.project_root)
                    )
                    pal.id_for((0, 0, 0, 0))  # reserve id 0 = empty tile
                palettes[pkey] = pal
            pal = palettes[pkey]

            # Register the layer in the global config (union across chunks).
            if key not in layers_config:
                layers_config[key] = {
                    "node_name": n.name,
                    "tileset": ts_path,
                    "z_index": info["z_index"],
                    "visible": info["visible"],
                    "role": LAYER_ROLE.get(key, "background"),
                    "palette": pkey,
                }
                layer_order.append(key)

            if not info["cells"]:
                continue  # empty layer: loader will create it empty
            grid = cells_to_grid(info["cells"], pal, GRID_W, GRID_H)
            if args.encoding == "rle":
                chunk_layers[key] = {
                    "encoding": "rle",
                    "data": grid_to_rle(grid),
                    "cells": len(info["cells"]),
                }
            else:
                chunk_layers[key] = {
                    "encoding": "grid",
                    "data": grid,
                    "cells": len(info["cells"]),
                }

        entities = extract_entities_from_nodes(nodes)
        if not entities and args.entities:
            entities = bin_world_entities(args.entities, col, row)

        chunk_json = {
            "schema_version": 1,
            "chunk_id": chunk_id,
            "grid_size": [GRID_W, GRID_H],
            "cell_size": CELL_SIZE,
            "empty_id": EMPTY_ID,
            "tile_id_map": args.map_res_path,
            "layers": chunk_layers,
            "entities": entities,
            "meta": {"source": f"res://{_rel(path, args.project_root)}"},
        }
        out_path = os.path.join(args.out_dir, chunk_id + ".json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(chunk_json, fh, separators=(",", ":"))
        exported.append({"chunk_id": chunk_id, "cells": sum(
            l["cells"] for l in chunk_layers.values())})

    # --- write the shared id map -------------------------------------------
    id_map = {
        "schema_version": 1,
        "cell_size": CELL_SIZE,
        "grid_size": [GRID_W, GRID_H],
        "empty_id": EMPTY_ID,
        "layer_order": layer_order,
        "layers": layers_config,
        "palettes": {k: p.to_json() for k, p in palettes.items()},
        "entity_prefabs": _merge_entity_prefabs(args.map_fs_path),
    }
    os.makedirs(os.path.dirname(args.map_fs_path), exist_ok=True)
    with open(args.map_fs_path, "w", encoding="utf-8") as fh:
        json.dump(id_map, fh, indent=2)

    print(f"Exported {len(exported)} chunks -> {args.out_dir}")
    for pkey, pal in palettes.items():
        print(f"  palette {pkey}: {len(pal.tiles)} distinct tiles")
    print(f"Wrote id map -> {args.map_fs_path}")
    return 0


def _merge_entity_prefabs(map_fs_path: str) -> dict:
    """Preserve user-edited entity_prefabs across re-exports; seed defaults."""
    merged = dict(DEFAULT_ENTITY_PREFABS)
    if os.path.isfile(map_fs_path):
        try:
            prev = json.load(open(map_fs_path, encoding="utf-8"))
            for k, v in prev.get("entity_prefabs", {}).items():
                merged[k] = v
        except (json.JSONDecodeError, OSError):
            pass
    return merged


def _res_to_fs(res_path: str, project_root: str) -> str:
    if res_path.startswith("res://"):
        return os.path.join(project_root, res_path[len("res://"):])
    return res_path


def _rel(fs_path: str, project_root: str) -> str:
    return os.path.relpath(fs_path, project_root).replace("\\", "/")


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chunks-dir", default="scenes/world/chunks")
    ap.add_argument("--tilesets-dir", default="assets/tilesets")
    ap.add_argument("--out-dir", default="assets/world/chunks_json")
    ap.add_argument("--map-out", default="assets/tilesets/tile_id_map.json",
                    help="Filesystem path for the generated id map.")
    ap.add_argument("--encoding", choices=["grid", "rle"], default="grid",
                    help="'grid' = dense 2D arrays (matches schema example, "
                         "larger); 'rle' = compact run-length (recommended for "
                         "the real 128x72 chunks).")
    ap.add_argument("--entities", default="",
                    help="Optional whole-world entities json to bin into chunks "
                         "(e.g. assets/world/s2_entities.json).")
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args(argv)

    args.project_root = os.path.abspath(args.project_root)
    args.chunks_dir = os.path.join(args.project_root, args.chunks_dir)
    args.tilesets_dir = os.path.join(args.project_root, args.tilesets_dir)
    args.out_dir = os.path.join(args.project_root, args.out_dir)
    args.map_fs_path = os.path.join(args.project_root, args.map_out)
    # res:// path the chunk JSON should record for the loader.
    args.map_res_path = "res://" + _rel(args.map_fs_path, args.project_root)
    if args.entities:
        args.entities = os.path.join(args.project_root, args.entities)
    return export(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
