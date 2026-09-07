# Saboteur 92

Mobile remake of **Saboteur** (1985) built with **Godot 4.6**.

## Requirements

- [Godot 4.6](https://godotengine.org/) with Mobile export support (`4.6.stable` / 4.6.0 — the version CI installs; `project.godot` `config/features` is `4.6`)
- Android SDK + JDK 17 (for Android builds)
- Android export templates installed in Godot
- Python 3.10+ and `pip install -r tools/requirements.txt` if you run the asset tools
- Optional Cursor MCP: copy `.cursor/mcp.json.example` to `.cursor/mcp.json` (gitignored) and replace the `C:\Path\To\...` placeholders with your Godot executable, this repo's `tools/aseprite-mcp/build/index.js`, and your `aseprite.exe`. The example uses `cmd /c` so it works in Cursor on Windows.

## Project structure

```text
scenes/          Game scenes (player, levels, UI, enemies, items)
scripts/         GDScript (player, AI, systems, items)
assets/          Sprites, tilesets, icons
exports/         Built APK/AAB output (gitignored)
```

## Art assets (Saboteur 1985 style)

Pixel art is generated programmatically to approximate the ZX Spectrum original:

```bash
pip install -r tools/requirements.txt
python tools/generate_saboteur85_assets.py
```

Outputs:
- `assets/sprites/saboteur85_player.png` — ninja (idle, run, jump, punch, climb, death)
- `assets/sprites/saboteur85_guard.png` — beret guard
- `assets/sprites/saboteur85_items.png` — key, document, bomb
- `assets/tilesets/saboteur85_tileset.png` — brick, floor, ladder, door, crate, window

Sprites render at 16x24 native pixels, scaled 3x in-game (nearest-neighbor).

## Run locally

1. Open the project in Godot 4.6
2. Press F5 or click **Play**
3. Controls:
   - Move: Arrow keys / WASD / touch ◀ ▶
   - Jump: Space / touch JMP
   - Punch: Z or X / touch HIT
   - Crouch: S or ▼ / touch ▼
   - Low punch: crouch, then HIT — stays crouched, hits knee height
   - High kick: HIT with ▲ held, or JMP + HIT standing still
   - Flying kick: HIT while already in the air
   - Long jump with a somersault: run, then JMP + HIT together (either order)
   - Climb ladders: W/S or ▲/▼ while on ladder
   - Optional phone tilt: tap **TILT** (top-right). Lean the screen's left or
     right edge down to walk that way; the angle you hold when you switch it on
     becomes neutral. ◀ ▶ still override the sensor, and the button reads
     `NO SENSOR` on a device that reports none. Off by default; the choice is
     saved. Needs `input_devices/sensors/enable_accelerometer` — Android only
     registers its sensor listener when that project setting is on.

## Mission flow

1. Pick up the **key**
2. Collect the **document** upstairs
3. Pick up the **bomb**
4. Plant the bomb at the sabotage target
5. Escape through the green exit before the timer ends

## Build Android APK

1. Install Android build template: **Editor → Manage Export Templates**
2. Configure SDK: **Editor → Editor Settings → Export → Android**
3. Open **Project → Export → Android**
4. Export to `exports/saboteur92.apk`

Debug builds use Gradle (`export_presets.cfg`).

### Package info

- Application ID: `com.saboteur92.game`
- Version: `0.1.0` (code 1)

Release signing uses a local keystore configured in Godot export settings. **Do not commit keystore files.**

## CI

GitHub Actions workflow `.github/workflows/android-export.yml` on push/PR: smoke run, mission playthrough (`--demo`), fuse-loss probe (`--demo-fuse`), tilt-steering probe (`--demo-tilt`, fakes the phone sensor with `Input.set_gravity`), collision audit, then a debug APK artifact.

## License

Game assets and code are part of the saboteur-92 project.
