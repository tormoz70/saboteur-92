# Agent handoff: restart context

Read this first when you continue the work in a new agent chat. The maze
exploration details are in [maze_exploration.md](maze_exploration.md). The
playable-build plan is [roadmap_v0.2.md](roadmap_v0.2.md).

## User and rules

- The user writes in Russian. Answer in Russian.
- Direction: a modern game, not a retro ZX clone. Take only the story,
  heroes and idea from Saboteur II. Sound, music, fonts, UI and art should
  look and sound modern; the current ZX beeper SFX, ZX font (`S2FONT.MAC`)
  and ZX-styled menus are placeholders to be replaced.
- Third-party assets: CC0 first; otherwise a licence that allows commercial
  store release without attribution. Record every file's source and licence
  in `assets/CREDITS.md`.
- Never use subagents or models with "Fast" in the name, or a slug ending in
  `-fast`, without explicit confirmation from the user.
- Never commit:
  - `.mcp/`;
  - the local `McpBridge` autoload line in `project.godot`;
  - `.godot/`.
- Commit or push only when the user asks. Stage files explicitly; don't use
  `git add -A`.
- CI is GitHub Actions `.github/workflows/android-export.yml`. It runs:
  - gdlint;
  - maze reachability (`tools/explore/check_reachability.py`);
  - chunk JSON `--check`;
  - GUT;
  - `--demo`, which must print `Mission complete`;
  - `--demo-fuse`, which must print `[Demo] Fuse loss OK`;
  - `--demo-tilt`;
  - the Android export.

## Environment

- Windows, PowerShell. Project: `C:\data\prjs\saboteur-92`.
- Godot 4.6: `.\tools\godot\Godot_v4.6-stable_win64.exe`.
- Lint:
  `python -m gdtoolkit.linter <files>`
- Tests:
  `& $g --headless -s addons/gut/gut_cmdln.gd -gexit`
- Reachability (no Godot; writes the nav graph to a temp dir):
  `python tools/explore/check_reachability.py`
- Demos:
  - `& $g --headless -- --demo`
  - `& $g --headless -- --demo-fuse`
  - `& $g --headless -- --demo-explore` (headless maze explorer, slow)

## Godot MCP (namespace `project-0-saboteur-92-godot`)

- `run_project {projectPath: "C:/data/prjs/saboteur-92"}`. The first try
  often reports that the bridge did not respond; just retry.
- The game starts on the title screen (`/root/Main`). Click `PlayButton`
  (`simulate_input` `click_element`) or pass `scene: "scenes/game.tscn"` to
  `run_project` to go straight in. The level is then `/root/Game/Level01`,
  and the player is `Level01/Player`.
- A windowed run autopauses when the game window loses focus. Resume with
  `scene_tree.current_scene.get_node("PauseMenu").resume_game()`.
- `run_script` needs a script that does `extends RefCounted` and defines
  `func execute(scene_tree: SceneTree) -> Variant`. `await
  scene_tree.physics_frame` works inside it, which is useful for frame traces.
- To attach the explorer:

  ```gdscript
  var lv := scene_tree.current_scene.get_node("Level01")
  var e := Node.new()
  e.name = "MazeExplorer"
  e.set_meta("manual", true)
  e.set_script(load("res://scripts/demo/explore_demo.gd"))
  lv.add_child(e)
  ```

- To query progress: `scene_tree.current_scene.get_node("Level01/MazeExplorer").coverage()`
  returns visited, done, ok/bad per edge type, rescues, and feet.
- The log comes from `get_debug_output`. Screenshots come from
  `take_screenshot`. Call `stop_project` when done.

## World and physics facts

- Chunks are 128×72 cells of 8 px, in `scenes/world/chunks`. The world grid
  is 1024×576 cells. Native px × 2 = world px.
- CollisionLayer tile: source 0. Atlas x gives the kind:
  - 1 = solid;
  - 1 with alt 1 = lift shaft (physics layer 32, ignored while riding);
  - 2 = ladder;
  - 3 = one-way;
  - 4 = rope (no physics polygon; `RopeController` runs along the top —
    stopping or reversing mid-span falls).
- User's map rules (judge on the chunk layers, not on the old
  `saboteur2_world2.png`, which still has baked guards):
  - blue brick (Wallpaper) is an open tunnel, black (Earth) is solid rock;
    every blue tunnel must be passable;
  - white metal beams are solid only when horizontal (heroes walk on them);
    vertical and diagonal beams are background and heroes pass through;
  - tightropes (red dotted lines on `saboteur2_world.png`) lead from the
    central complex to the radio tower (y 672) and to the left antenna
    (y 960).
- Player body: 14×42 at (24, 35). Feet = origin + 56 native. Body x = origin
  + 24 native.
- Speeds: walk 110, gravity 820. Step-up is 20 world px. Collision is off
  while on a ladder or rope.
- Somersault: moving plus a fresh up tap. A standing up tap is a kick.
- The game has exactly three lifts, the cyan-railed tubes on the fan map:
  x 2600 (y 960–2272, locked by the crate code), x 3624 (2400–3712) and
  x 5416 (1968–3280). One cabin each, stops only at the two stations.
  Nina rides by standing centred on the cabin (±24 world px) and pressing up
  or down.
- Each station has a call console (`lift_panels` in `s2_entities.json`,
  `LiftPanel`): any punch or kick on it sends the idle cabin to that station
  (`Lift.summon`; the locked lift needs the code). The cabin going down has
  no collision; going up it is solid and carries Nina if she drops onto it.
  The console at (6784, 1408) is the fence terminal, not a lift panel.
- Tube walls are rock and the top station is an open tube: the parked cabin
  is the floor, and with the cabin away Nina falls down the shaft (no fall
  damage). No alt 1 cells remain. `python tools/explore/patch_lift_collision.py`
  rebuilds that from `lifts` in `s2_collision.json`; `build_nav.py` treats
  the top station row as floor.
- A lift cabin uses `sync_to_physics`: `global_position` is stale after a move
  within the same frame. Use `Lift.cabin_y()` while it is moving.
- `lifts` and `bookcases` in `s2_collision.json` came from the bytecode
  layout (x +256 from the fan map) and were fixed by hand.
  `check_reachability.py` fails if a cabin or a shaft end is not flush on a
  floor, a top station tube is not open, a lift panel names no lift or floats,
  a bookcase shelf (Structure `(6,0)`) has collision, or an ink rect misses
  its bookcase.

## Sound

- Autoload `AudioManager` (`scripts/systems/audio_manager.gd`): buses
  Master / SFX / Music (`default_bus_layout.tres`), an 8-player SFX pool,
  `play_sfx(name)`, looping theme + `theme_fast` while the dump fuse runs.
  Volume helpers (`set_sfx_volume` / `set_music_volume`) are ready for the
  Stage 4 settings shell. Safe under the Dummy audio driver (headless).
- Mission events wire through `EventBus` (pickup, alarm, death, win, bomb
  planted → urgent music + fuse tick). Movement SFX are direct calls from
  `player.gd`, `ladder_controller.gd`, `lift.gd`, `rope_controller.gd`.
- Effects and music are CC0 recordings (Kenney, OpenGameArt), not the old
  ZX beeper. Provenance is `assets/CREDITS.md`. Rebuild the WAVs from the
  raw downloads in `assets/audio/_source/` (gitignored):
  `python tools/process_audio.py`
  Needs `numpy` and `miniaudio` (`pip install numpy miniaudio`). No ffmpeg.
  Effects are 22050 Hz, 16-bit mono. Music is 44100 Hz, 16-bit stereo;
  `theme_fast` is the same track sped up 1.4×. Then import once so `.import`
  files refresh:
  `& $g --headless --path . --import`

## Shell (title, pause, settings, results)

- `scenes/main.tscn` is the title screen (`scripts/ui/title_screen.gd`).
  "Play" resets `GameManager` and changes to `scenes/game.tscn`.
- `scenes/game.tscn` (`scripts/ui/game.gd`) holds `Level01`, `HUD`,
  `TouchControls`, `ResultScreen`, `PauseMenu`, `SettingsMenu`, and a
  `Loading` curtain that lifts on `LevelBase.world_ready`. That is also when
  `GameManager.start_clock()` starts `mission_time`. "Play again" is
  `GameManager.restart_mission()`, which reloads this scene, so it skips the
  title.
- Demo flags (`TitleScreen.DEMO_ARGS`: `--demo`, `--demo-fuse`,
  `--demo-tilt`, `--demo-maze`, `--demo-explore`) make the title jump straight
  to `game.tscn`. `tools/capture_map_view.gd` and `tools/verify_entities.gd`
  load `game.tscn` directly.
- Pause (`scripts/ui/pause_menu.gd`, `process_mode` ALWAYS) is
  `get_tree().paused` plus `AudioManager.set_paused`. It is triggered by the
  HUD "II" button, `ui_cancel`, Android back, and autopause on
  `NOTIFICATION_APPLICATION_PAUSED` / `FOCUS_OUT`. Autopause is off under the
  headless display server, with demo flags, and in `GameManager.demo_mode`.
  A `SceneTreeTimer` that must stop with the pause needs
  `create_timer(t, false)`.
- Settings: autoload `GameSettings` (`scripts/systems/game_settings.gd`).
  - Stored in `user://settings.cfg`: `[audio] sfx_volume, music_volume` and
    `[controls] tilt_sensitivity, pad_scale, pad_opacity`.
  - `TiltSteer` still owns `[controls] tilt_steer`. Both sides reload the
    file before saving.
  - Values apply the moment they change. Tests point both at a temp file
    with `GameSettings.use_config_path()`.
- Records: `MissionRecords` (`scripts/systems/mission_records.gd`) keeps
  `user://records.cfg` `[lab_mission] best_time, best_time_alarmed,
  best_score, wins`. A worse run never overwrites a better one, and demo wins
  are not recorded.
- UI look: `assets/ui/zx_theme.tres` (Spectrum palette, `HudButton`
  variation for in-game buttons). Its font is `assets/ui/zx_font.fnt`,
  generated from the Saboteur II charset by `python tools/generate_zx_font.py`.
  The font is ASCII only, so menu text is English. Its import uses integer
  scaling, so keep font sizes at multiples of 8.

## Enemies

- Shared senses: `EnemySenses` (`scripts/enemies/enemy_senses.gd`).
  - Sight is `SightArea` overlap, then rays on WORLD | LIFT_SHAFT to Nina's
    chest and head. The rays hop past one-way cells; ladders and ropes
    have no physics, so only solid tiles block the view.
  - `ledge_ahead` / `wall_ahead` are `test_move` probes one body width
    ahead. A lift cabin under the probe counts as a ledge.
- Guard (`scripts/enemies/guard.gd`, exports and consts at the top):
  - States: PATROL → NOTICE (stands still, shows the "!" `AlertMark`, plays
    SFX `spotted`, `notice_time` 0.4 s) → CHASE → WINDUP (leans back and
    flushes red, `attack_windup` 0.4 s) → RECOVER (0.45 s).
  - The wind-up starts with Nina within `attack_range` 45 world px. The
    blow lands at its end only if she is still up to `attack_reach` 52 px
    ahead and within 45 px vertically. Damage is 15.
  - Speeds (world px/s): patrol 60, chase 100; Nina walks at 110. Health 2.
    A hit staggers it for 0.35 s.
  - It turns at walls, ledges and `patrol_distance`. In a chase it stops at
    the edge instead of falling.
  - The alarm goes off after `ALARM_CHASE_SEC` 1.0 s engaged (CHASE, WINDUP
    or RECOVER). Fuse is 50 s, capped at 35 s by the alarm
    (`GameManager.ALARM_FUSE_CAP`).
- Panther (`scripts/enemies/panther.gd`, `scenes/enemies/panther.tscn`):
  - States: PROWL (140) → CHARGE (175) on sight. It turns back to Nina only
    after she has been behind it for `turn_delay` 0.5 s, so a somersault
    over it buys time.
  - Touch (`HurtBox` 40×18 native, 18 px high) deals 15, with a 0.6 s
    cooldown. It turns at walls and ledges and never leaves its floor.
  - Health 2: the first hit stuns it for 0.6 s, the second kills it (+100).
    Only the crouch punch reaches it; the standing punch goes over its back.
  - Spawns come from `panthers` in `assets/world/s2_entities.json` (native
    px, top-left of the 64×32 frame, `patrol` 0 = the whole floor). They
    reach chunk JSON as the `panther` prefab through
    `tools/export_chunks_to_json.py`.
  - Sprite: `python tools/generate_panther_sprite.py` →
    `assets/sprites/saboteur92_panther.png` (4 run frames + crouch).
- Tests: `test/unit/test_guard.gd` and `test_panther.gd` build small
  collision arenas with `test/enemy_arena.gd`. `tools/verify_entities.gd`
  checks that every panther lands on its floor.

## Next steps

Follow [roadmap_v0.2.md](roadmap_v0.2.md). Stages 1–5 (reachability, rope,
sound, shell, enemies) are done; next is the real-device pass.
