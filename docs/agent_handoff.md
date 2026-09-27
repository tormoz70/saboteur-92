# Agent handoff: restart context

Read this first when you continue the work in a new agent chat. The maze
exploration details are in [maze_exploration.md](maze_exploration.md). The
playable-build plan is [roadmap_v0.2.md](roadmap_v0.2.md).

## User and rules

- The user writes in Russian. Answer in Russian.
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
- Lifts stop only at the shaft ends. Nina rides by standing centred on the
  cabin (±24 world px) and pressing up or down.
- A lift cabin uses `sync_to_physics`: `global_position` is stale after a move
  within the same frame. Use `Lift.cabin_y()` while it is moving.

## Sound

- Autoload `AudioManager` (`scripts/systems/audio_manager.gd`): buses
  Master / SFX / Music (`default_bus_layout.tres`), an 8-player SFX pool,
  `play_sfx(name)`, looping theme + `theme_fast` while the dump fuse runs.
  Volume helpers (`set_sfx_volume` / `set_music_volume`) are ready for the
  Stage 4 settings shell. Safe under the Dummy audio driver (headless).
- Mission events wire through `EventBus` (pickup, alarm, death, win, bomb
  planted → urgent music + fuse tick). Movement SFX are direct calls from
  `player.gd`, `ladder_controller.gd`, `lift.gd`, `rope_controller.gd`.
- Regenerate WAV (22050 Hz, 16-bit mono, deterministic):
  `python tools/generate_sfx.py`
  Then import once so `.import` files appear:
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

## Next steps

Follow [roadmap_v0.2.md](roadmap_v0.2.md). Stages 1–4 (reachability, rope,
sound, shell) are done; next open stages are enemies, then a real-device
pass.
