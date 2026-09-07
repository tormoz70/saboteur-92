# Saboteur rip pipeline

Scripts in this folder rebuild sprites, tilesets and the Saboteur II world from
original dumps. Those dumps are **local developer reference only** — they stay
out of git (`assets/reference/` is in `.gitignore`) and they must not ship in
the APK. See `docs/remediation_plan.md`, stage 5.

Game runtime does **not** need this folder. Collision, tilesets and mission
entities under `assets/world/` and `assets/tilesets/` are already committed.
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
| `build_s2_world.py` | `maps/Saboteur2_speccy.png` | `assets/world/s2_collision.json`, `assets/tilesets/s2_world_tileset.png` (+ fg atlas) |
| `build_s2_world.py --ladders-only` | mosaic, or committed tileset if the rip is absent | only the `ladders` array in `s2_collision.json` |
| `audit_collision.py` | committed `s2_collision.json` + tileset PNG | stdout report (no dumps required) |
| `extract_from_tap.py` | `SABOTEU1.TAP`, `sabot1core.asm` | `ripped/` |
| `extract_from_disasm.py` | `sabot1core.asm` | `ripped/` |
| `extract_from_z80.py` | `snap/SABOTEUR.Z80` | `extracted/` |
| `extract_masked.py` | `snap/SABOTEUR.Z80` | `extracted/masked/` |
| `extract_scr.py` | any `*.scr` / `*.SCR` next to the TAP | `extracted/` |
| `extract_split.py` | snapshot via `extract_from_z80` | split frames |
| `curate_refs.py` | `extracted/split/` | `curated/` |
| `extract_saboteur2.py` | `SABOT2-DISASM/*.MAC` + `SpriteRotate/` | `ripped_s2/` + in-game sheets |
| `extract_s2_map.py` | `S2ROOM.MAC` | `maps/` JSON index |
| `build_game_sheets.py` | `ripped/` | `assets/sprites/` |
| `build_saboteur93_player.py` | `ripped/` | player sheet |

`tools/generate_saboteur85_assets.py` (repo root `tools/`) is a separate
programmatic ZX-style generator. It does not read `assets/reference/`.

## Typical world rebuild

```bash
pip install -r tools/requirements.txt
python tools/saboteur_rip/build_s2_world.py
python tools/saboteur_rip/audit_collision.py
```

Without the mosaic PNG the first command only re-exports tilesets. To refresh
climb zones from the committed visual tileset (green rails, white X-lattice,
and the white-on-blue sky pair):

```bash
python tools/saboteur_rip/build_s2_world.py --ladders-only
```

To mark the white diamond slabs (interior room dividers and outdoor girder
decks) and cave-tunnel floors/ceilings (including flooded black corridors
between brick masses) as walkable solids, punch decorative red support
posts, and clear blue-brick wallpaper plus crates so they are never walls,
without growing those slabs downward:

```bash
python tools/saboteur_rip/build_s2_world.py --floors-only
```

Without the mosaic PNG the first command only re-exports tilesets.
`--ladders-only` and `--floors-only` still work from the committed visual
tileset and rewrite `s2_collision.json`.
