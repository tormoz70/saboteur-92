# World Chunk ↔ JSON Bridge

A two-way bridge between native Godot chunk scenes and an LLM-friendly JSON
format, so new levels can be authored/generated as plain integer grids and
rebuilt at runtime.

```
scenes/world/chunks/*.tscn  ──(export_chunks_to_json.py)──►  assets/world/chunks_json/*.json
                                                             assets/tilesets/tile_id_map.json
assets/world/chunks_json/*.json  ──(WorldBuilder.gd)──►  Node2D (TileMapLayers + entities)
                                 ──(ChunkValidator.gd)─►  solvability pre-check
```

## Files

| Piece | Path | Role |
|---|---|---|
| JSON Schema | `docs/world_chunk_schema.json` | Strict schema for one chunk (draft-07). |
| Exporter | `tools/export_chunks_to_json.py` | Godot → JSON. Pure std-lib. |
| ID map (generated) | `assets/tilesets/tile_id_map.json` | Palette + layer + prefab lookup. |
| Loader | `scripts/world/world_builder.gd` | JSON → Node2D at runtime. |
| Validator | `scripts/world/chunk_validator.gd` | Build-free A*/BFS solvability check. |

## How the real data maps to the schema

The Saboteur-92 chunks are **not** the idealized single-`TileMap` example from
the brief; the bridge is built around the actual project:

- **8×8 chunk grid**, each chunk **128×72 cells @ 8 px** (`grid_size`, `cell_size`).
- Tiles live in the Godot 4.3+ `TileMapLayer.tile_map_data` **PackedByteArray**
  (2-byte header + 12-byte cells `[x,y,source_id,atlas_x,atlas_y,alt]`, LE).
  The exporter decodes this directly — no GDScript dump helper needed.
- There is **no single master TileSet**. Each layer uses its own `.tres`
  (earth / structure / wallpaper / mosaic / interior / fg / collision), so the
  ID map is **per-layer / per-TileSet**, not one global palette.
- `source_id` is always `0`; a tile's identity is its **atlas coordinate**.
- Collision semantics live in a dedicated **`collision`** layer whose TileSet
  has a `collision_type` custom-data layer (`empty/solid/ladder/oneway/rope`).
  The exporter reads those strings into `palettes.*.collision_types`, which is
  what the validator walks.
- Chunks currently contain **no entity nodes**; entities are optionally binned
  in from `assets/world/s2_entities.json` (`--entities`).

## ID mapping configuration (`tile_id_map.json`)

This is the lookup table that makes simplified integer ids reversible. It is
**generated** by the exporter (so ids always match the data) and **consumed**
by both the loader and validator.

```jsonc
{
  "cell_size": 8,
  "grid_size": [128, 72],
  "empty_id": -1,
  "layer_order": ["earth","structure","wallpaper","mosaic",
                  "interior1","interior2","structure_front","foreground","collision"],

  // layer key -> which Godot node + TileSet + z-order it rebuilds as
  "layers": {
    "earth": { "node_name": "Earth", "tileset": "res://assets/tilesets/s2_earth_tileset.tres",
               "z_index": -20, "visible": true, "role": "terrain", "palette": "s2_earth_tileset" }
    // ...
  },

  // palette key -> distinct tiles. index in `tiles` == the integer id used in a
  // layer grid. tile = [source_id, atlas_x, atlas_y, alternative_tile]
  "palettes": {
    "s2_earth_tileset": { "tile_size": [8,8], "tiles": [[0,1,0,0]] },
    "s2_collision_tileset": {
      "tile_size": [8,8],
      "tiles": [[0,0,0,0],[0,3,0,0],[0,1,0,0],[0,2,0,0],[0,4,0,0],[0,1,0,1]],
      "collision_types": ["empty","oneway","solid","ladder","rope","solid"]
    }
  },

  // logical entity type -> prefab. Hand-edit freely; re-export preserves edits.
  "entity_prefabs": {
    "spawn": "", "guard": "res://scenes/enemies/guard.tscn",
    "key_item": "res://scenes/items/pickup.tscn",
    "exit": "res://scenes/items/exit_zone.tscn"
  }
}
```

**Why this shape:** a layer grid stores only small ints; `layers[key].palette`
picks the palette; `palettes[palette].tiles[id]` gives the exact atlas tile to
restore. Nothing is hardcoded — point the layers at different `.tres` files or
add tiles and everything else follows. Re-exporting is stable: existing tiles
keep their ids (append-only), and your `entity_prefabs` edits are preserved.

## Usage

### Export (Godot → JSON)

```bash
# Compact run-length encoding (recommended for the real 128×72 chunks)
python tools/export_chunks_to_json.py --encoding rle \
    --entities assets/world/s2_entities.json

# Dense 2D arrays (matches the schema example; larger files)
python tools/export_chunks_to_json.py --encoding grid
```

### Load (JSON → scene) at runtime

```gdscript
var root := WorldBuilder.build_from_file(
    "res://assets/world/chunks_json/chunk_03_03.json")
add_child(root)                       # ready-to-use Node2D
root.position = Vector2(col, row) * Vector2(128 * 8, 72 * 8)
```

Or from an in-memory dict straight off an LLM:

```gdscript
var builder := WorldBuilder.new()      # instance caches TileSets across chunks
var root := builder.build(chunk_dict)  # id map loaded from chunk_dict.tile_id_map
```

### Validate before building

```gdscript
var chunk := JSON.parse_string(FileAccess.get_file_as_string(path)) as Dictionary
var idmap := JSON.parse_string(FileAccess.get_file_as_string(
    "res://assets/tilesets/tile_id_map.json")) as Dictionary

var r := ChunkValidator.validate_chunk_connectivity(chunk, idmap)
# r = { ok, errors, reachable, unreachable_exits }
if not r.ok:
    push_warning("reject chunk: %s" % str(r.errors))
```

## Solvability / pathfinding prep

Because the `collision` layer is a semantic integer grid, solvability is a
**graph-reachability** question we answer without building a scene:

1. Decode the `collision` layer → a `width×height` grid of type strings.
2. Mark `solid`/`oneway` as walls; `ladder`/`rope` as climbable; `empty` as air.
3. Flood-fill (BFS) from entry cells using platformer moves — walk, single-cell
   step-up, climb ladders/ropes, fall through air — and check every exit is
   reached. `MAX_STEP_UP` bounds ledge climbing.

This is the cheap gate in a **generate → validate → repair** loop for the AI
generator: reject unreachable exits and sealed pockets in microseconds before
paying to instantiate anything. For precise navigation later, the same grid
feeds Godot's `AStarGrid2D` (solid cells = `set_point_solid`).

## Verified

- All **64/64** chunks export and reconstruct **byte-identical** to their
  `.tscn` cell data (palette + RLE round-trip).
- `world_builder.gd` and `chunk_validator.gd` pass headless Godot 4.6 parse
  validation.
