# AI World Generator — Plan

Roadmap for a data-driven, AI-authored level pipeline for Saboteur-92. The
foundation (a two-way JSON↔Godot chunk bridge with a validator) is merged; the
rest builds the generate → validate → repair → assemble loop on top of it.

## Ground truth (project reality)

- World = **8×8 chunk grid**; each chunk **128×72 cells @ 8 px**; tile coords are
  chunk-local. World placement: `chunk.position = (col,row) * (128*8, 72*8)`
  under `WorldMap`, which is scaled ×2 (`level_01.tscn`).
- Tiles live in `TileMapLayer.tile_map_data` (Godot 4.3+ PackedByteArray:
  2-byte header + 12-byte cells `[x,y,source_id,atlas_x,atlas_y,alt]`, LE).
  Godot serializes it as base64 for long arrays and as a decimal byte list for
  short ones.
- **No master TileSet** — 7 per-layer `.tres` (earth/structure/wallpaper/mosaic/
  interior/fg/collision). `source_id` always 0; tile identity = atlas coords +
  alternative (which carries flip/transpose bits).
- Collision semantics on the dedicated `collision` layer via `collision_type`
  custom-data (`empty/solid/ladder/oneway/rope`).
- Entities are **not** in chunk scenes; they live in
  `assets/world/s2_entities.json` (whole-world png px, actors by sprite
  top-left). Lifts live in `assets/world/s2_collision.json` (`lifts`: `x`,
  `top`, `bottom` in png px; shafts span several chunks).
- Runtime: `LevelBase` + `level_01.gd` instance chunks from
  `scenes/world/chunks/chunks.json`; ladders/lifts/entities are built in
  `LevelBase` from the JSON files above, not from chunk JSON.
- Player body 14×42 px (crouch 14×24), plain jump ~22 px up / ~36 px across,
  ladder hatches up to 20 px (`LadderController.RUNG_PAD_NATIVE`).

## Stage 0 — Bridge foundation ✅ DONE (PR #26, merged `e6a4d33`)

- `docs/world_chunk_schema.json` — draft-07 schema; payload shape per
  `encoding`, layer keys restricted, entity params named after prefab props.
- `tools/export_chunks_to_json.py` — `.tscn` → JSON; reads both
  PackedByteArray forms, fails instead of dropping cells; **append-only**
  palette ids; full entity export; `--check` for staleness.
- `scripts/world/world_builder.gd` — JSON → `Node2D`; strict layer decode;
  entities from `entity_prefabs` with game property names, `world_scale` for
  native-px params, params kept as node metadata.
- `scripts/world/chunk_validator.gd` — structural checks + reachability flood
  with a player-sized body (crawl, jumps, oneway, hatches, `links`); ~25 ms/chunk.
- Generated: `assets/tilesets/tile_id_map.json`, `assets/world/chunks_json/*`.
- CI: `.github/workflows/world_chunks.yml` runs `--check`.

## Stage 1 — In-engine validation of the loader

- [x] Headless check that WorldBuilder rebuilds every `.tscn` chunk: GUT
  `test_world_builder.gd` compares all 64 chunks cell-for-cell (613 418 cells,
  plus z-index, visibility, TileSet, node order).
- [x] GUT `test_world_builder.gd`: entity nodes get correct prefab,
  position, `item_type`, scaled `patrol_distance`; unknown types → Marker2D.
- [x] GUT `test_chunk_validator.gd`: sealed room, low gaps, jump gaps and
  ledges, hatches, oneway floors, links, malformed payloads; real map: spawn
  reaches the key, every ladder shaft climbable.
- [ ] Integrate `WorldBuilder` as an optional path in `level_01.gd`
  (`_load_world`) behind a flag, loading `chunks_json/*` instead of `.tscn`.
  Build tiles only: `LevelBase` still spawns entities from
  `s2_entities.json`, so skip chunk entities (or switch the source) to avoid
  double spawns. Run the mission demo (`--demo`) on the JSON path in CI.
- [ ] Measure JSON-path load time against the `.tscn` path (the `.tscn` path
  already needs `CHUNKS_PER_FRAME` batching to stay responsive).

## Stage 2 — Constraint/palette contract for the LLM

- [ ] Emit a **compact palette catalog** for prompting: per layer, a short list
  of allowed tile ids + human labels (floor, wall, ladder, door, crate…),
  derived from `tile_id_map.json` + a small hand-authored label map.
- [ ] Define **authoring rules** the model must follow (chunk = 128×72; collision
  layer required; ladders connect floors; hatch lids ≤ 2 cells; rooms at least
  6 cells tall where the player walks, 3 where it crawls).
- [ ] Add a `tools/build_palette_catalog.py` that produces
  `assets/world/palette_catalog.json` (labels) for prompt construction.
- [ ] Decide whether generated chunks carry their entities or whether
  entities stay world-level (`s2_entities.json`); today both exist and only
  the world file drives the game.

## Stage 3 — Generation loop

- [ ] `tools/generate_chunk.py`: prompt an LLM with schema + palette catalog +
  neighbor edge constraints → candidate chunk JSON.
- [ ] Validate candidates **without porting the validator**: a headless
  `tools/validate_chunks.gd` runner (`godot --headless -s ...`) that reads
  chunk JSON and prints `{ok, errors, unreachable_exits}` as JSON, called from
  Python. One implementation keeps the model and the tests in sync; revisit a
  Python port only if process start-up dominates the loop.
- [ ] Feed `errors` / `unreachable_exits` back to the model; the validator's
  messages already name the layer, cell and rule.
- [ ] **Repair pass**: carve minimal ladders/openings for small failures before
  re-prompting.
- [ ] **Edge stitching**: constrain each chunk's border cells to match adjacent
  chunks so seams (floors, tunnels, ladder shafts) line up across the 8×8 grid.

## Stage 4 — Assembly & authoring UX

- [ ] **World-level reachability**: stitch the 64 collision grids into one
  1024×576 grid (or flood across chunk borders) so routes that cross chunks
  validate; today out-of-chunk cells count as walls/sky.
- [ ] Derive validator `links` from world data: a lift in
  `s2_collision.json` connects every standable floor along its shaft between
  `top` and `bottom`; each `passages` entry in `s2_entities.json` connects its
  position to `to_x`/`to_y`. (`bookcases` there are only ink-outline rects,
  not passages.)
- [ ] `tools/assemble_world.py`: validate a full 8×8 set with one reachable
  objective chain (spawn → key → document → bomb → sabotage → exit), then
  write `chunks_json/*` + a manifest mirroring `chunks.json`.
- [ ] Optional `tools/import_json_to_tscn.py` (JSON → `.tscn`) so generated
  levels can be opened/edited in the Godot editor (round-trips the bridge).
- [ ] Editor plugin or CLI: preview a generated chunk, run the validator, show
  reachability overlay.

## Validator model — known gaps

Deliberate or not-yet-modelled; each can produce a wrong verdict:

- Somersault long jumps (~5 cells up, ~10 across) are ignored, so some
  passable gaps are rejected (conservative).
- Lifts only via `links` (Stage 4); guards, doors, interlocks and the lift code
  are not considered.
- The body is a box on the cell grid; sub-cell geometry and slopes are not.

## Design invariants (don't break)

- Keep the **id map generated, not hand-maintained**; ids are append-only so
  re-export is stable. Never delete `tile_id_map.json` to "clean up": it
  renumbers every palette. `entity_prefabs` edits are preserved.
- `.tscn` chunks are the source of truth for the shipped world; chunk JSON is
  regenerated from them and CI fails if it is stale.
- Nothing hardcodes a TileSet; layer→TileSet and id→atlas come from the config.
- Collision is the **authoritative** walkability layer; visual layers never
  affect pathfinding.
- Positions in chunk JSON: tiles and entities in cells (loader ×cell_size);
  px-valued params stay native px and are listed in `entity_scaled_params`.

## Key references

- Bridge guide: `docs/world_chunk_bridge.md`
- Tests: `test/unit/test_world_builder.gd`, `test/unit/test_chunk_validator.gd`
- Byte format + collision constants: `scripts/world/tilemap_utils.gd`
- Ladder/hatch rules: `scripts/player/ladder_controller.gd`
- Runtime chunk loading: `scripts/levels/level_01.gd`, `scripts/levels/level_base.gd`
- Entities and passages: `assets/world/s2_entities.json`; lifts: `assets/world/s2_collision.json`
