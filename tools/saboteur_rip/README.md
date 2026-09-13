# Saboteur rip pipeline

Sprite extractors in this folder rebuild character and item sheets from
original dumps. Those dumps are **local developer reference only** — they stay
out of git (`assets/reference/` is in `.gitignore`) and they must not ship in
the APK.

World tilesets, tile JSON and the old world parse/generate scripts were cleared
on `refactor/tilemap-migration`. They will be rebuilt from scratch.

Game runtime does **not** need this folder.

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
| `extract_from_tap.py` | `SABOTEU1.TAP`, `sabot1core.asm` | `ripped/` |
| `extract_from_disasm.py` | `sabot1core.asm` | `ripped/` |
| `extract_from_z80.py` | `snap/SABOTEUR.Z80` | `extracted/` |
| `extract_masked.py` | `snap/SABOTEUR.Z80` | `extracted/masked/` |
| `extract_scr.py` | any `*.scr` / `*.SCR` next to the TAP | `extracted/` |
| `extract_split.py` | snapshot via `extract_from_z80` | split frames |
| `curate_refs.py` | `extracted/split/` | `curated/` |
| `extract_saboteur2.py` | `SABOT2-DISASM/*.MAC` + `SpriteRotate/` | `ripped_s2/` + in-game sheets (includes SOM1C–SOM4C as `nina_somersault_1..4`) |
| `tools/sprites/build_player_moves.py` | player sheet + optional ripped SOM frames | `saboteur93_player_moves.png` |
| `build_game_sheets.py` | `ripped/` | `assets/sprites/` |
| `build_saboteur93_player.py` | `ripped/` | player sheet |

`tools/generate_saboteur85_assets.py` (repo root `tools/`) is a separate
programmatic ZX-style generator. It does not read `assets/reference/`.
