# Saboteur rip pipeline

Scripts in this folder rebuild sprites, tilesets and the Saboteur II world from
original dumps. Those dumps are **local developer reference only** — they stay
out of git (`assets/reference/` is in `.gitignore`) and they must not ship in
the APK. See `docs/remediation_plan.md`, stage 5.

Game runtime does **not** need this folder. Collision, object sprites and mission
entities under `assets/world/` are already committed.
`tools/saboteur_rip/audit_collision.py` also runs against those committed
files, so CI does not need the dumps.

## Layout to drop dumps into

Place originals here (paths are as the scripts resolve them from the repo root):

```
assets/reference/original/
├── SABOTEU1.TAP                          # Saboteur (1985) tape
├── sabot1core.asm                        # Saboteur (1985) disassembly
├── snap/SABOTEUR.Z80                     # Spectrum snapshot
├── maps/Saboteur2_speccy.png             # stitched Saboteur II mosaic
└── s2/
    ├── ms0515-various/SABOT2-DISASM/
    │   ├── S2ROOM.MAC                    # room grid (SMAP)
    │   ├── S2SPRT.MAC                    # character tiles / BCHRS
    │   ├── S24C72.MAC                    # Nina sprite maps
    │   ├── S29DE4.MAC                    # Nina tile bytes
    │   └── S2ITEM.MAC                    # items
    └── bk0011m-saboteur2/SpriteRotate/   # nzeemin 8x8 ink sheets
```

Optional / generated under the same tree (scripts create these, do not commit):

```
assets/reference/original/
├── ripped/                               # extract_from_tap / extract_from_disasm
├── ripped_s2/                            # extract_saboteur2
├── extracted/                            # extract_from_z80 / extract_scr / extract_masked
└── curated/                              # curate_refs
```

Python paths are already portable: `ROOT = Path(__file__).resolve().parents[2]`.

## Dependencies

From the repo root:

```bash
pip install -r tools/requirements.txt
```

That is Pillow only. The rest of the toolchain is the Python standard library.

## What reads what

| Script | Needs | Writes |
|---|---|---|
| `decompose_world.py` | `S2ROOM.MAC` + `S2CORE.MAC` + `S2SPRT.MAC` (+ mosaic to verify / crop empty prefabs) | `s2_objects.json` (types+instances), `objects/<layer>/*.png`, `s2_collision.json` (`collision_source: object_bounds`), `s2_collision_tiles.json` |
| `collision_tiles.py` | committed `s2_collision.json` + `s2_world_tiles.json` | `s2_collision_tiles.json`, `s2_collision_tileset.*`, `test/fixtures/screen_spawn_tiles.json`, `scenes/levels/screen_spawn.tscn` |
| `build_s2_world.py` | same (wrapper) | calls `decompose_world.main()` — mosaic colour heuristics are retired |
| `test_room_bytecode.py` | disasm | stdout (246 rooms, SMAP, ladders) |
| `test_role_collision.py` | none | stdout (marker collision + hatch stamp) |
| `test_world_layers.py` | committed `s2_objects.json` | stdout (registry layers / sprites) |
| `audit_collision.py` | committed `s2_collision.json` | stdout report (no dumps required) |
| `labyrinth.py` / `test_labyrinth.py` | committed collision tiles + entities | stdout: floors/ladders/spawn hold; reachability report |
| `extract_from_tap.py` | `SABOTEU1.TAP`, `sabot1core.asm` | `ripped/` |
| `extract_from_disasm.py` | `sabot1core.asm` | `ripped/` |
| `extract_from_z80.py` | `snap/SABOTEUR.Z80` | `extracted/` |
| `extract_masked.py` | `snap/SABOTEUR.Z80` | `extracted/masked/` |
| `extract_scr.py` | any `*.scr` / `*.SCR` next to the TAP | `extracted/` |
| `extract_split.py` | snapshot via `extract_from_z80` | split frames |
| `curate_refs.py` | `extracted/split/` | `curated/` |
| `extract_saboteur2.py` | `SABOT2-DISASM/*.MAC` + `SpriteRotate/` | `ripped_s2/` + in-game sheets (includes SOM1C–SOM4C as `nina_somersault_1..4`) |
| `tools/sprites/build_player_moves.py` | player sheet + optional ripped SOM frames | `saboteur93_player_moves.png` |
| `extract_s2_map.py` | `S2ROOM.MAC` | `maps/` JSON index |
| `build_game_sheets.py` | `ripped/` | `assets/sprites/` |
| `build_saboteur93_player.py` | `ripped/` | player sheet |

`tools/generate_saboteur85_assets.py` (repo root `tools/`) is a separate
programmatic ZX-style generator. It does not read `assets/reference/`.

## Typical world rebuild

```bash
pip install -r tools/requirements.txt
python tools/saboteur_rip/decompose_world.py
python tools/saboteur_rip/collision_tiles.py
python tools/saboteur_rip/test_collision_tiles.py
python tools/saboteur_rip/test_room_bytecode.py
```

`build_s2_world.py` is a compatibility wrapper around the same decompose step.
Colour-heuristic flags (`--ladders-only`, `--floors-only`) are retired.
