# Saboteur 92

Mobile remake of **Saboteur** (1985) built with **Godot 4.6**.

## Requirements

- [Godot 4.6](https://godotengine.org/) with Mobile export support
- Android SDK + JDK 17 (for Android builds)
- Android export templates installed in Godot

## Project structure

```text
scenes/          Game scenes (player, levels, UI, enemies, items)
scripts/         GDScript (player, AI, systems, items)
assets/          Sprites, tilesets, icons
exports/         Built APK/AAB output (gitignored)
```

## Run locally

1. Open the project in Godot 4.6
2. Press F5 or click **Play**
3. Controls:
   - Move: Arrow keys / WASD / touch ◀ ▶
   - Jump: Space / touch JMP
   - Punch: Z or X / touch HIT
   - Climb ladders: W/S or ▲/▼ while on ladder

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

GitHub Actions workflow `.github/workflows/android-export.yml` exports a debug APK on push/PR and uploads it as an artifact.

## License

Game assets and code are part of the saboteur-92 project.
