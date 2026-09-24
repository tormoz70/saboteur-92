# Agent handoff: restart context

Read this first when you continue the work in a new agent chat. The maze
exploration details are in [maze_exploration.md](maze_exploration.md).

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
- Tests, which print `Passing Tests 111`:
  `& $g --headless -s addons/gut/gut_cmdln.gd -gexit`
- Demos:
  - `& $g --headless -- --demo`
  - `& $g --headless -- --demo-fuse`
  - `& $g --headless -- --demo-explore` (headless maze explorer, slow)

## Godot MCP (namespace `project-0-saboteur-92-godot`)

- `run_project {projectPath: "C:/data/prjs/saboteur-92"}`. The first try
  often reports that the bridge did not respond; just retry.
- The game starts in `Main`. The level is `/root/Main/Level01`, and the
  player is `Level01/Player`.
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
  - 4 = rope (no physics, and no real ropes exist).
- Player body: 14×42 at (24, 35). Feet = origin + 56 native. Body x = origin
  + 24 native.
- Speeds: walk 110, gravity 820. Step-up is 20 world px. Collision is off
  while on a ladder.
- Somersault: moving plus a fresh up tap. A standing up tap is a kick.
- Lifts stop only at the shaft ends. Nina rides by standing centred on the
  cabin (±24 world px) and pressing up or down.
- A lift cabin uses `sync_to_physics`: `global_position` is stale after a move
  within the same frame. Use `Lift.cabin_y()` while it is moving.

## Uncommitted work (current state)

Modified:

- `scripts/world/lift.gd`: `_y` and `cabin_y()` (end-stop departure fix) and
  `carries()`.
- `scripts/player/lift_rider.gd`: fallback floor-flush detection of the cabin.
- `assets/world/s2_collision.json`: lift cabin y snapped to the shaft floor
  rows.
- `assets/world/s2_entities.json`: `locked_lift` y changed from 2264 to 2280.
- `scripts/levels/level_base.gd`: the `--demo-explore` flag.

New:

- `scripts/demo/explore_demo.gd` (and `.uid`): the in-game explorer.
- `tools/explore/build_nav.py`: builds the nav graph into
  `.mcp/explore/nav_graph.json`.
- `tools/explore/nav_reach.py`: computes reachability and renders the
  coverage PNG.
- `docs/maze_exploration.md` and `docs/maze_coverage.png`: the progress
  report.
- `coverage.png`: a root copy of the map. It can be deleted.

Note: `explore_demo.gd` reads `res://.mcp/explore/nav_graph.json`. That path
is untracked, so the graph must be rebuilt with `build_nav.py` before a run.

All checks passed after these changes: GUT 111/111, `--demo`,
`--demo-fuse`, and gdlint.

Helper scripts, untracked, live in `.mcp/screenshots/`:

- `colgrid.py`: builds the grid and saves `colgrid.npy`. Codes: 0 empty,
  1 solid, 5 shaft, 2 ladder, 3 one-way, 4 rope.
- `_lifts.py` and `_lifts_fix.py`.
- `_ascii.py` and `_nav_dbg.py`.

## Last result

- Visited 3674 of 4666 nodes (78.7%). The graph can reach 4162 (89.2%).
- Rescues: 426.
- Lift rides: 4 ok and 2 failed, after the fix.

## Next steps (in priority order)

1. **Explorer climb landing** (`_run_climb` SETTLE in `explore_demo.gd`):
   - Problem: it accepts arrival while Nina is still `on_ladder` under the
     floor. She then walks off and falls down the hatch.
   - Fix: require `not _player.on_ladder` and `is_on_floor()`, and nudge
     up or sideways to dismount.
2. **Jumps:** 32 of 103 missed. Tune the takeoff in `_run_jump`, or align
   the arc simulation in `build_nav.py`.
3. **Walk edges:** those that need a step-up above 20 world px fail with
   "wrong floor". Tighten the walk adjacency in `build_nav.py`.
4. **Re-run and compare coverage:**
   - `build_nav.py`;
   - run through MCP and wait for `done`;
   - `nav_reach.py`;
   - copy the PNG to `docs/maze_coverage.png` and update the report.
5. **Map fixes, only if the user wants them:**
   - the solid blobs in the bottom tunnel (x ≈ 2368, 1648–1704, 432–456 at
     y ≈ 3960–3984);
   - the stale bookcase passage coordinates.

   Use the `edit-world-chunks` skill for chunk edits.
6. **Commit only when the user asks.** Exclude `.mcp/`, `.godot/`, and the
   `McpBridge` line. Decide with the user whether `coverage.png` goes in.
