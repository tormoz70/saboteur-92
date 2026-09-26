# World Chunk ↔ JSON Bridge

A two-way bridge between native Godot chunk scenes and an LLM-friendly JSON
format, so new levels can be authored/generated as plain integer grids and
rebuilt at runtime.

```
scenes/world/chunks/*.tscn  ──(export_chunks_to_json.py)──►  assets/world/chunks_json/*.json
                                                             assets/tilesets/tile_id_map.json
assets/world/chunks_json/*.json  ──(WorldBuilder.gd)──►  Node2D (TileMapLayers + entities)
                                 ──(ChunkValidator.gd)─►  structure + reachability pre-check
```

## Files

| Piece | Path | Role |
|---|---|---|
| JSON Schema | `docs/world_chunk_schema.json` | Schema for one chunk (draft-07). |
| Exporter | `tools/export_chunks_to_json.py` | Godot → JSON. Pure std-lib. |
| ID map (generated) | `assets/tilesets/tile_id_map.json` | Palette + layer + prefab lookup. |
| Loader | `scripts/world/world_builder.gd` | JSON → Node2D at runtime. |
| Validator | `scripts/world/chunk_validator.gd` | Build-free structure and reachability check. |
| Tests | `test/unit/test_chunk_validator.gd`, `test/unit/test_world_builder.gd` | GUT. |
| CI | `.github/workflows/world_chunks.yml` | Fails when chunk JSON is stale. |

## How the real data maps to the schema

The Saboteur-92 chunks are **not** the idealized single-`TileMap` example from
the brief; the bridge is built around the actual project:

- **8×8 chunk grid**, each chunk **128×72 cells @ 8 px** (`grid_size`, `cell_size`).
- Tiles live in the Godot 4.3+ `TileMapLayer.tile_map_data` **PackedByteArray**
  (2-byte format header + 12-byte cells `[x,y,source_id,atlas_x,atlas_y,alt]`, LE).
  Godot writes it as base64 for long arrays and as a decimal byte list for
  short ones; the exporter reads both and fails on anything else instead of
  dropping cells.
- There is **no single master TileSet**. Each layer uses its own `.tres`
  (earth / structure / wallpaper / mosaic / interior / fg / collision), so the
  ID map is **per-layer / per-TileSet**, not one global palette.
- `source_id` is always `0`; a tile's identity is its **atlas coordinate** plus
  `alternative_tile`, which also carries the flip/transpose bits
  (e.g. `20480` = transpose + flip H).
- Collision semantics live in a dedicated **`collision`** layer whose TileSet
  has a `collision_type` custom-data layer (`empty/solid/ladder/oneway/rope`).
  The exporter reads those strings into `palettes.*.collision_types`, which is
  what the validator walks.
- Chunks contain **no entity nodes**; entities are binned in from
  `assets/world/s2_entities.json` (see below).

## ID mapping configuration (`tile_id_map.json`)

This is the lookup table that makes simplified integer ids reversible. It is
**generated** by the exporter and **consumed** by the loader and validator.

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
    "s2_earth_tileset": { "tile_size": [8, 8], "tiles": [[0, 1, 0, 0]] },
    "s2_collision_tileset": {
      "tile_size": [8, 8],
      "tiles": [[0, 0, 0, 0], [0, 3, 0, 0], [0, 1, 0, 0], [0, 2, 0, 0], [0, 4, 0, 0], [0, 1, 0, 1]],
      "collision_types": ["empty", "oneway", "solid", "ladder", "rope", "solid"]
    }
  },

  // logical entity type -> prefab. "" = no prefab on purpose (Marker2D).
  // Hand-edit freely; re-export preserves edits.
  "entity_prefabs": {
    "spawn": "", "guard": "res://scenes/enemies/guard.tscn",
    "key": "res://scenes/items/pickup.tscn", "invuln": "res://scenes/items/pickup.tscn",
    "exit": "res://scenes/items/exit_zone.tscn", "marker": ""
    // ...
  },

  // native-px params the game compares against global coords
  "entity_scaled_params": ["patrol_distance"]
}
```

**Why this shape:** a layer grid stores only small ints; `layers[key].palette`
picks the palette; `palettes[palette].tiles[id]` gives the exact atlas tile to
restore.

**Ids are append-only.** The exporter loads the existing `tile_id_map.json`
first: known tiles keep their ids, new tiles get the next free id, and palettes
no chunk uses any more stay in the map. Chunk JSON authored against an older
map (for example by the AI generator) therefore stays valid after a
re-export. Deleting `tile_id_map.json` resets the numbering and invalidates
every chunk authored outside the `.tscn` set; don't do it casually.

## Entities

`s2_entities.json` is authored in whole-world native ("png") pixels. Each
entity lands in the chunk whose rectangle contains it, in chunk-local cells.
Params use the game's property names (see `LevelBase._spawn_entities`), so
WorldBuilder can set them verbatim:

| type | params | prefab |
|---|---|---|
| `spawn` | `origin`, `size_px` | Marker2D |
| `guard`, `alarm_guard` | `patrol_distance` (native px), `origin`, `size_px`; alarm guard also `spawn_on: "alarm"` | `guard.tscn` |
| `key`, `document`, `bomb`, `invuln` | `item_type`, `required_item` | `pickup.tscn` |
| `sabotage_target` | `bomb_fuse_time` (world-level fuse) | `sabotage_target.tscn` |
| `exit` | — | `exit_zone.tscn` |
| `marker`, `interlock`, `locked_lift`, `passage` | `label` / `to`, `need_crouch` | Marker2D |

`origin: "top_left"` marks actors positioned by their 48×56 sprite's top-left,
as in `s2_entities.json`; pickups, sabotage and exit are Area2D centres.

WorldBuilder puts every entity under `Entities/`, named by its `id` (or type),
and stores `entity_type` / `entity_params` as node metadata. That is how level
code wires the prefab-less types and world-level fields like
`bomb_fuse_time`. A type missing from `entity_prefabs`, a missing prefab file
or a prefab whose root is not a `Node2D` becomes a Marker2D with a warning.

## Usage

### Export (Godot → JSON)

```bash
python tools/export_chunks_to_json.py           # rle + s2_entities.json (defaults)
python tools/export_chunks_to_json.py --check   # exit 1 if any JSON is stale (CI)
python tools/export_chunks_to_json.py --encoding grid   # dense rows, larger files
```

Output is indented JSON with each layer payload on one line (one line per row
for `grid`), so diffs point at the layer that changed. The exporter fails,
writing nothing, on an unreadable `tile_map_data`, cells outside 128×72, an
unknown layer node, or layer settings that differ between chunks.

### Load (JSON → scene) at runtime

```gdscript
# level_01 adds chunks under WorldMap, which is scaled x2
var root := WorldBuilder.build_from_file(
    "res://assets/world/chunks_json/chunk_03_03.json", {}, 2.0)
root.position = Vector2(col, row) * Vector2(128 * 8, 72 * 8)
world_map.add_child(root)
```

Or from an in-memory dict straight off an LLM:

```gdscript
var builder := WorldBuilder.new()      # instance caches TileSets across chunks
builder.world_scale = 2.0              # scale of the parent node
var root := builder.build(chunk_dict)  # id map loaded from chunk_dict.tile_id_map
```

A malformed layer payload or an out-of-palette id rejects that layer with a
`push_error` (the layer stays empty) instead of building half of it.

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

`entries` / `exits` default to the chunk's `spawn` / `exit` entities. In the
real map these sit in different chunks, so for a single chunk pass the points
you care about explicitly, e.g. the chunk's door cells.

## What the validator checks

**Structure:** layer keys known to the id map; `rle` payloads with even
length, counts ≥ 1 and exactly width×height cells; `grid` payloads with
exactly `height` rows of `width` ids; every id inside its palette.

**Reachability** is a flood fill over the `collision` grid with a body-sized
agent (defaults from `player.gd`, all overridable through `options`):

| option | default | from |
|---|---|---|
| `agent_width` × `agent_height` | 2 × 6 cells | `BODY_STAND_SIZE` 14×42 px |
| `crouch_height` | 3 cells | `BODY_CROUCH_SIZE` 14×24 px |
| `jump_up` / `jump_across` | 2 / 4 cells | plain jump: ~22 px up, ~36 px across |
| `hatch_thickness` | 2 cells | `LadderController.RUNG_PAD_NATIVE` 20 px |
| `links` | `[]` | lifts, passages: `[[[x1, y1], [x2, y2]], ...]` |

Solid blocks the body; oneway only supports from above; ladders and ropes
never block (the ladder controller turns collisions off). Moves: walk or
crawl one cell, fall until landing, climb, climb through a hatch lid, and
jump (rise, drift sideways at that height, fall). An exit counts as reached
when a reachable body box covers it; nothing is found through a floor.

**Not modelled (by design, or not yet):** somersault long jumps (the check
stays conservative), lifts unless passed as `links`, guards and other
dynamic hazards, cross-chunk routes (out-of-chunk cells are walls on the
sides and bottom and open sky above). About 25 ms per chunk.

For precise navigation later, the same grid feeds Godot's `AStarGrid2D`
(solid cells = `set_point_solid`).

## Verified

- All 64 chunks rebuild through WorldBuilder cell-for-cell identical to their
  `.tscn` (613 418 cells, with layer z-index, visibility, TileSet and node
  order): `test_world_builder.gd`.
- Validator: sealed rooms, low gaps, jump gaps and ledges, hatches, oneway
  floors, links and malformed payloads in `test_chunk_validator.gd`. On the
  real map, spawn reaches the key in `chunk_02_01`, and every ladder shaft
  (with a hatch lid of at most 2 cells) is climbable from its bottom.
- `python tools/export_chunks_to_json.py --check` passes on the committed files.
