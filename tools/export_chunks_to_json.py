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
        tile_map_data = PackedByteArray("<base64>")      (long arrays)
        tile_map_data = PackedByteArray(0, 0, 3, 0, ...) (short arrays)
    Godot picks the form by size, so both must be read. Layout (little-endian):
        bytes[0:2]   uint16 format header (must be 0)
        then repeated 12-byte cells:
            int16  x            (chunk-local cell x)
            int16  y            (chunk-local cell y)
            uint16 source_id    (always 0 in this project)
            uint16 atlas_x
            uint16 atlas_y
            uint16 alternative_tile  (includes TRANSFORM_FLIP_H/V/TRANSPOSE bits)
    Older/empty chunks simply omit the property. Anything else is an error:
    the exporter refuses to guess rather than silently drop cells.

Tile identity is (source_id, atlas_x, atlas_y, alternative). This exporter
assigns each *distinct* tile a small sequential PALETTE id (0..N) per TileSet,
writing the lookup table to tile_id_map.json so WorldBuilder.gd can map ids
back to atlas coordinates. Palettes are APPEND-ONLY: an existing
tile_id_map.json is loaded first, known tiles keep their ids and new tiles are
appended, so chunk JSON authored against an older map stays valid.

Usage:
    python tools/export_chunks_to_json.py            # write chunks + id map
    python tools/export_chunks_to_json.py --check    # exit 1 if files are stale
    options: [--encoding rle|grid] [--entities assets/world/s2_entities.json]
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
TILE_MAP_DATA_FORMAT = 0
SCHEMA_VERSION = 1

# Godot node name -> layer key (snake_case) used in the JSON schema. The order
# is the node order inside the chunk scenes and becomes `layer_order`.
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

PICKUP_SCENE = "res://scenes/items/pickup.tscn"
GUARD_SCENE = "res://scenes/enemies/guard.tscn"

# Default logical-type -> prefab map seeded into tile_id_map.json. Edit freely;
# the exporter only *seeds* missing keys, it never overwrites your edits.
# "" = no prefab on purpose: WorldBuilder drops a Marker2D carrying the params
# as metadata, and the level wires it up (markers, interlock, passages, ...).
DEFAULT_ENTITY_PREFABS = {
    "spawn": "",
    "guard": GUARD_SCENE,
    "alarm_guard": GUARD_SCENE,
    "key": PICKUP_SCENE,
    "document": PICKUP_SCENE,
    "bomb": PICKUP_SCENE,
    "invuln": PICKUP_SCENE,
    "sabotage_target": "res://scenes/items/sabotage_target.tscn",
    "exit": "res://scenes/items/exit_zone.tscn",
    "marker": "",
    "interlock": "",
    "locked_lift": "",
    "passage": "",
}

# Entity params stored in native (PNG) pixels that the game compares against
# global coordinates; WorldBuilder multiplies them by its world_scale.
ENTITY_SCALED_PARAMS = ["patrol_distance"]

# Player and guard origins in s2_entities.json are the sprite's top-left.
ACTOR_SPRITE_PX = [48, 56]


# --- .tscn / .tres parsing ---------------------------------------------------

@dataclass
class TscnNode:
    name: str
    type: str
    parent: Optional[str]
    body: str


class ExportError(Exception):
    pass


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


def parse_packed_byte_array(literal: str) -> bytes:
    """Contents of `PackedByteArray(...)`: a quoted base64 string or a
    comma-separated list of decimal bytes (Godot writes short arrays so)."""
    s = literal.strip()
    if not s:
        return b""
    if s.startswith('"') and s.endswith('"'):
        return base64.b64decode(s[1:-1])
    try:
        return bytes(int(v) for v in s.split(","))
    except ValueError as exc:
        raise ExportError(f"unrecognised PackedByteArray literal: {s[:40]}...") from exc


def decode_tile_map_data(raw: bytes) -> list[tuple[int, int, int, int, int, int]]:
    """Decode a TileMapLayer tile_map_data blob into (x,y,src,ax,ay,alt)."""
    cells: list[tuple[int, int, int, int, int, int]] = []
    if not raw:
        return cells
    if len(raw) < 2:
        raise ExportError("tile_map_data shorter than its header")
    (fmt,) = struct.unpack_from("<H", raw, 0)
    if fmt != TILE_MAP_DATA_FORMAT:
        raise ExportError(f"unsupported tile_map_data format {fmt}")
    if (len(raw) - 2) % 12:
        raise ExportError(f"tile_map_data size {len(raw)} is not 2 + 12*n")
    for off in range(2, len(raw), 12):
        cells.append(struct.unpack_from("<hhHHHH", raw, off))
    return cells


def extract_layer(node: TscnNode) -> dict:
    """Pull tile cells + presentation props from a TileMapLayer node body."""
    cells = []
    if re.search(r'^\s*tile_map_data\s*=', node.body, re.M):
        dm = re.search(r'tile_map_data\s*=\s*PackedByteArray\(([^)]*)\)', node.body)
        if not dm:
            raise ExportError(f"layer {node.name}: tile_map_data is not a PackedByteArray")
        try:
            cells = decode_tile_map_data(parse_packed_byte_array(dm.group(1)))
        except ExportError as exc:
            raise ExportError(f"layer {node.name}: {exc}") from exc
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
    with open(tres_path, encoding="utf-8") as fh:
        txt = fh.read()
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
    is_collision: bool = False
    _custom: dict[tuple[int, int, int], str] = field(default_factory=dict)

    def id_for(self, tile: tuple[int, int, int, int]) -> int:
        if tile not in self._index:
            self._index[tile] = len(self.tiles)
            self.tiles.append(tile)
        return self._index[tile]

    def seed(self, tiles: list) -> None:
        """Pre-load ids from a previous tile_id_map.json (append-only ids)."""
        for t in tiles:
            self.id_for(tuple(int(v) for v in t))

    def to_json(self) -> dict:
        out = {
            "tileset": self.tileset_path,
            "tile_size": self.tile_size,
            "tiles": [list(t) for t in self.tiles],
        }
        if self.is_collision:
            out["collision_types"] = [
                self._custom.get((ax, ay, alt), "empty")
                for (_src, ax, ay, alt) in self.tiles
            ]
        return out


def palette_key(tileset_path: str) -> str:
    """Stable palette key = tileset file stem, e.g. 's2_earth_tileset'."""
    return os.path.splitext(os.path.basename(tileset_path))[0]


# --- Grid encoding -----------------------------------------------------------

def cells_to_grid(cells, palette: Palette, w: int, h: int) -> tuple[list[list[int]], int]:
    """Returns (grid, out_of_bounds_count)."""
    grid = [[EMPTY_ID] * w for _ in range(h)]
    oob = 0
    for (x, y, src, ax, ay, alt) in cells:
        if 0 <= x < w and 0 <= y < h:
            grid[y][x] = palette.id_for((src, ax, ay, alt))
        else:
            oob += 1
    return grid, oob


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


def bin_world_entities(data: dict, chunk_col: int, chunk_row: int) -> list[dict]:
    """Slice a whole-world s2_entities.json into this chunk.

    s2_entities.json stores positions in whole-world *native* pixels ("png"
    coord space). An entity is in chunk (col,row) if its px falls inside the
    chunk rectangle; it is written in chunk-local CELL coordinates. Param names
    match the game's node properties (see LevelBase._spawn_entities) so
    WorldBuilder can apply them verbatim; px-valued ones stay native px.
    """
    chunk_px_w = GRID_W * CELL_SIZE
    chunk_px_h = GRID_H * CELL_SIZE
    x0 = chunk_col * chunk_px_w
    y0 = chunk_row * chunk_px_h
    out: list[dict] = []

    def to_cells(x: float, y: float) -> list[float]:
        return [round((x - x0) / CELL_SIZE, 3), round((y - y0) / CELL_SIZE, 3)]

    def emit(etype: str, spec, params: dict, eid: str = "") -> None:
        if isinstance(spec, list):
            x, y = float(spec[0]), float(spec[1])
        else:
            x, y = float(spec["x"]), float(spec["y"])
        if not (x0 <= x < x0 + chunk_px_w and y0 <= y < y0 + chunk_px_h):
            return
        rec = {"type": etype, "position": to_cells(x, y), "params": params}
        if eid:
            rec["id"] = eid
        out.append(rec)

    def actor(params: dict) -> dict:
        return {**params, "origin": "top_left", "size_px": list(ACTOR_SPRITE_PX)}

    sp = data.get("spawn")
    if isinstance(sp, list) and len(sp) >= 2:
        emit("spawn", sp, actor({}))
    for it in data.get("items", []):
        itype = it.get("type", "key")
        emit(itype, it, {"item_type": itype, "required_item": it.get("required", "")},
             it.get("id", ""))
    for g in data.get("guards", []):
        emit("guard", g, actor({"patrol_distance": g.get("patrol", 40)}), g.get("id", ""))
    ag = data.get("alarm_guard")
    if isinstance(ag, dict) and "x" in ag:
        emit("alarm_guard", ag,
             actor({"patrol_distance": ag.get("patrol", 40), "spawn_on": "alarm"}))
    sab = data.get("sabotage")
    if isinstance(sab, dict) and "x" in sab:
        params = {"bomb_fuse_time": data["fuse"]} if "fuse" in data else {}
        emit("sabotage_target", sab, params)
    ex = data.get("exit")
    if isinstance(ex, dict) and "x" in ex:
        emit("exit", ex, {})
    for m in data.get("markers", []):
        emit("marker", m, {"label": m.get("label", "")}, m.get("id", ""))
    for p in data.get("passages", []):
        emit("passage", p, {
            "to": to_cells(float(p.get("to_x", p["x"])), float(p.get("to_y", p["y"]))),
            "need_crouch": bool(p.get("need_crouch", True)),
        }, p.get("id", ""))
    il = data.get("interlock")
    if isinstance(il, dict) and "x" in il:
        emit("interlock", il, {})
    ll = data.get("locked_lift")
    if isinstance(ll, dict) and "x" in ll:
        emit("locked_lift", ll, {})
    return out


# --- Output formatting -------------------------------------------------------

def dump_chunk(chunk: dict) -> str:
    """Pretty JSON with each layer's payload kept compact: one line per RLE
    layer / grid row, so git diffs point at the layer that changed."""
    placeholders: dict[str, str] = {}
    shallow = dict(chunk)
    shallow["layers"] = {}
    for key, layer in chunk["layers"].items():
        token = f"@@DATA_{key}@@"
        if layer["encoding"] == "grid":
            rows = ",\n        ".join(json.dumps(r, separators=(",", ":")) for r in layer["data"])
            placeholders[token] = "[\n        " + rows + "\n      ]"
        else:
            placeholders[token] = json.dumps(layer["data"], separators=(",", ":"))
        shallow["layers"][key] = {**layer, "data": token}
    text = _inline_pairs(json.dumps(shallow, indent=2))
    for token, payload in placeholders.items():
        text = text.replace(f'"{token}"', payload)
    return text + "\n"


def dump_id_map(id_map: dict) -> str:
    """Indented JSON, but palette tiles stay one `[src,ax,ay,alt]` per line."""
    text = json.dumps(id_map, indent=2)
    text = re.sub(
        r"\[\s*(-?\d+),\s*(-?\d+),\s*(-?\d+),\s*(-?\d+)\s*\]",
        r"[\1, \2, \3, \4]",
        text,
    )
    return _inline_pairs(text) + "\n"


def _inline_pairs(text: str) -> str:
    """`[\\n  128,\\n  72\\n]` -> `[128, 72]` for sizes and positions."""
    return re.sub(r"\[\s*(-?[\d.]+),\s*(-?[\d.]+)\s*\]", r"[\1, \2]", text)


# --- Main export -------------------------------------------------------------

def chunk_col_row(chunk_id: str) -> tuple[int, int]:
    m = re.search(r'(\d+)_(\d+)$', chunk_id)
    return (int(m.group(1)), int(m.group(2))) if m else (0, 0)


def _load_json(path: str) -> dict:
    if not os.path.isfile(path):
        return {}
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def export(args: argparse.Namespace) -> int:
    chunk_files = sorted(
        f for f in os.listdir(args.chunks_dir) if f.endswith(".tscn")
    )
    if not chunk_files:
        print(f"No .tscn files in {args.chunks_dir}", file=sys.stderr)
        return 1

    prev_map = _load_json(args.map_fs_path)
    prev_palettes = prev_map.get("palettes", {})
    world_entities = _load_json(args.entities) if args.entities else {}

    palettes: dict[str, Palette] = {}
    layers_config: dict[str, dict] = {}
    outputs: dict[str, str] = {}
    errors: list[str] = []

    for fname in chunk_files:
        path = os.path.join(args.chunks_dir, fname)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()
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
                errors.append(f"{fname}: unknown TileMapLayer '{n.name}'")
                continue
            try:
                info = extract_layer(n)
            except ExportError as exc:
                errors.append(f"{fname}: {exc}")
                continue
            ts_path = ext.get(info["tileset_ext_id"], "")
            pkey = palette_key(ts_path) if ts_path else key
            if pkey not in palettes:
                is_col = key == "collision"
                fs_ts = _res_to_fs(ts_path, args.project_root)
                pal = Palette(
                    tileset_path=ts_path,
                    tile_size=parse_tileset_tile_size(fs_ts),
                    is_collision=is_col,
                )
                if is_col:
                    pal._custom = parse_tileset_custom_data(fs_ts)
                    pal.id_for((0, 0, 0, 0))  # id 0 = the tileset's "empty" tile
                pal.seed(prev_palettes.get(pkey, {}).get("tiles", []))
                palettes[pkey] = pal
            pal = palettes[pkey]

            cfg = {
                "node_name": n.name,
                "tileset": ts_path,
                "z_index": info["z_index"],
                "visible": info["visible"],
                "role": LAYER_ROLE.get(key, "background"),
                "palette": pkey,
            }
            if key not in layers_config:
                layers_config[key] = cfg
            elif layers_config[key] != cfg:
                errors.append(f"{fname}: layer '{n.name}' differs from other chunks "
                              f"({cfg} vs {layers_config[key]})")

            if not info["cells"]:
                continue  # empty layer: loader will create it empty
            grid, oob = cells_to_grid(info["cells"], pal, GRID_W, GRID_H)
            if oob:
                errors.append(f"{fname}: layer '{n.name}' has {oob} cell(s) outside "
                              f"{GRID_W}x{GRID_H}")
            chunk_layers[key] = {
                "encoding": args.encoding,
                "data": grid_to_rle(grid) if args.encoding == "rle" else grid,
                "cells": len(info["cells"]) - oob,
            }

        entities = extract_entities_from_nodes(nodes)
        if not entities and world_entities:
            entities = bin_world_entities(world_entities, col, row)

        chunk_json = {
            "schema_version": SCHEMA_VERSION,
            "chunk_id": chunk_id,
            "grid_size": [GRID_W, GRID_H],
            "cell_size": CELL_SIZE,
            "empty_id": EMPTY_ID,
            "tile_id_map": args.map_res_path,
            "layers": chunk_layers,
            "entities": entities,
            "meta": {"source": f"res://{_rel(path, args.project_root)}"},
        }
        outputs[os.path.join(args.out_dir, chunk_id + ".json")] = dump_chunk(chunk_json)

    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Palettes from the previous map that no chunk uses any more are kept, so
    # their ids stay reserved for chunks authored outside the .tscn set.
    for pkey, prev in prev_palettes.items():
        if pkey not in palettes:
            pal = Palette(tileset_path=prev.get("tileset", ""),
                          tile_size=prev.get("tile_size", [CELL_SIZE, CELL_SIZE]))
            pal.seed(prev.get("tiles", []))
            palettes[pkey] = pal

    layer_order = [k for k in NODE_TO_KEY.values() if k in layers_config]
    id_map = {
        "schema_version": SCHEMA_VERSION,
        "cell_size": CELL_SIZE,
        "grid_size": [GRID_W, GRID_H],
        "empty_id": EMPTY_ID,
        "layer_order": layer_order,
        "layers": {k: layers_config[k] for k in layer_order},
        "palettes": {k: p.to_json() for k, p in palettes.items()},
        "entity_prefabs": _merge_entity_prefabs(prev_map),
        "entity_scaled_params": list(ENTITY_SCALED_PARAMS),
    }
    outputs[args.map_fs_path] = dump_id_map(id_map)

    if args.check:
        return _check(outputs, args.out_dir)

    os.makedirs(args.out_dir, exist_ok=True)
    os.makedirs(os.path.dirname(args.map_fs_path), exist_ok=True)
    for out_path, content in outputs.items():
        with open(out_path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)

    print(f"Exported {len(chunk_files)} chunks -> {args.out_dir}")
    for pkey, pal in palettes.items():
        print(f"  palette {pkey}: {len(pal.tiles)} distinct tiles")
    print(f"Wrote id map -> {args.map_fs_path}")
    return 0


def _check(outputs: dict[str, str], out_dir: str) -> int:
    stale: list[str] = []
    for out_path, content in outputs.items():
        current = None
        if os.path.isfile(out_path):
            with open(out_path, encoding="utf-8") as fh:
                current = fh.read()
        if current != content:
            stale.append(out_path)
    expected = {os.path.normcase(p) for p in outputs}
    if os.path.isdir(out_dir):
        for f in os.listdir(out_dir):
            p = os.path.join(out_dir, f)
            if f.endswith(".json") and os.path.normcase(p) not in expected:
                stale.append(p + " (no source .tscn)")
    if stale:
        print("Chunk JSON is out of date; re-run tools/export_chunks_to_json.py:",
              file=sys.stderr)
        for p in stale:
            print(f"  {p}", file=sys.stderr)
        return 1
    print(f"OK: {len(outputs)} files up to date")
    return 0


def _merge_entity_prefabs(prev_map: dict) -> dict:
    """Preserve user-edited entity_prefabs across re-exports; seed defaults."""
    merged = dict(DEFAULT_ENTITY_PREFABS)
    merged.update(prev_map.get("entity_prefabs", {}))
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
    ap.add_argument("--out-dir", default="assets/world/chunks_json")
    ap.add_argument("--map-out", default="assets/tilesets/tile_id_map.json",
                    help="Filesystem path for the generated id map.")
    ap.add_argument("--encoding", choices=["grid", "rle"], default="rle",
                    help="'rle' = compact run-length (default, used for the "
                         "committed chunks); 'grid' = dense 2D arrays.")
    ap.add_argument("--entities", default="assets/world/s2_entities.json",
                    help="Whole-world entities json to bin into chunks; '' to skip.")
    ap.add_argument("--check", action="store_true",
                    help="Do not write; exit 1 if any generated file is stale.")
    ap.add_argument("--project-root", default=".")
    args = ap.parse_args(argv)

    args.project_root = os.path.abspath(args.project_root)
    args.chunks_dir = os.path.join(args.project_root, args.chunks_dir)
    args.out_dir = os.path.join(args.project_root, args.out_dir)
    args.map_fs_path = os.path.join(args.project_root, args.map_out)
    # res:// path the chunk JSON should record for the loader.
    args.map_res_path = "res://" + _rel(args.map_fs_path, args.project_root)
    if args.entities:
        args.entities = os.path.join(args.project_root, args.entities)
    return export(args)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
