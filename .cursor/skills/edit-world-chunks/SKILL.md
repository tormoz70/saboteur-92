---
name: edit-world-chunks
description: >-
  Observe and edit Saboteur II world chunk TileMaps through Godot MCP.
  Finds and erases baked ZX figures (guards, panthers) split across Mosaic,
  Wallpaper, Interior, and Structure; restores wallpaper and furniture from a
  clean twin; lifts furniture parts baked into the wall (desk/chair legs stuck
  on Mosaic) onto Interior as transparent tiles; saves with editor undo. Use
  when the user edits chunks, paints TileMap, asks to watch Godot, says a desk
  or prop fell apart across two layers, or asks to remove baked
  guards/sprites from mosaic, wallpaper, interior, or structure layers.
---

# Edit world chunks via Godot MCP

Map lives in `scenes/world/chunks/chunk_XX_YY.tscn` (128×72 cells, 8 px).
Do not rebuild chunks with `tools/build_world_chunks.gd` after a hand edit.

## MCP session

Namespace: `project-0-saboteur-92-godot` (`godot-mcp-runtime`).

1. If tools are missing: Customize → MCP → enable **godot**.
2. The bridge is hosted by the editor plugin `addons/mcp_bridge`, which loads
   `res://mcp_bridge.gd` **at editor start**. That file is gitignored and is
   often absent — then nothing listens on `127.0.0.1:35676` and every
   `run_script` fails with `ECONNREFUSED`.
3. Restore it before launching the editor: copy
   `<node_modules>/godot-mcp-runtime/dist/scripts/mcp_bridge.gd`, replace
   `const PORT := 9900` with `35676`, write **UTF-8 without BOM**
   (`[System.IO.File]::WriteAllText` with `UTF8Encoding($false)`; PowerShell
   `Set-Content -Encoding UTF8` adds a BOM and GDScript then fails to load).
4. Restart the editor — the plugin only reads the file in `_enter_tree()`.
   Touching `plugin.gd` does not hot-reload it. Wait ~20 s, then confirm
   `netstat -ano | findstr LISTENING | findstr 35676` before attaching.
   `launch_editor` returns before the process is up; do not launch a second
   editor on the same project while checking.
5. `attach_project` with `bridgePort` 35676 and `projectPath` in the **exact
   case Godot reports** (`C:\data\prjs\saboteur-92`). A case mismatch answers
   `Bridge reports project C:/... expected c:/...`, and the server then shuts
   the bridge down **and deletes `mcp_bridge.gd`**. Any failed attach deletes
   it, so rewrite the file before every restart.
6. If attach writes `McpBridge=...` into `project.godot`, **revert that line**
   (`git checkout -- project.godot`). The editor plugin already hosts the
   bridge; a second autoload is wrong.
7. `take_screenshot` times out in the editor. Capture via `run_script` instead.
8. `open_scene_from_path` switches at most about five scenes inside one
   `run_script`; the next call returns and the edited scene stays put.
   Batch chunk edits by three. The edit is idempotent, so a stopped batch
   can be rerun.

`run_script` must `extends RefCounted` and define
`func execute(scene_tree: SceneTree) -> Variant`.

Do not call `Engine.get_singleton` (blocked). Use `EditorInterface` by name.
Never `await RenderingServer.frame_post_draw` — an unfocused editor does not
redraw and the call hangs until the 30 s tool timeout.

## Observe the 2D view

`EditorInterface.get_editor_viewport_2d().get_canvas_transform()` is often
identity. Zoom/pan is in `get_final_transform()`:

```
var vp := EditorInterface.get_editor_viewport_2d()
var world: Vector2 = vp.get_final_transform().affine_inverse() * (Vector2(vp.size) * 0.5)
var cell := layer.local_to_map(world)
```

Save a PNG from `vp.get_texture().get_image()`. For a figure bbox, blit 8×8
atlas tiles from `assets/tilesets/s2_*_tileset.png` (PIL nearest-scale) so
Interior overlays Mosaic/Wallpaper, Structure under both.

`EditorInterface.get_edited_scene_root()`, `get_open_scenes()`,
`get_selection()` report what the human is looking at.

If editor undo does nothing after a bad save: `git checkout --` the chunk
`.tscn`, then `EditorInterface.reload_scene_from_path(...)`.

## Layers

| Layer | Fill / keep | Figure leftovers |
|---|---|---|
| Mosaic | HQ greek-key `(1,0)`; panel stripes `(2,0)`/`(3,0)` — never overwrite stripes | unique atlas + holes under Interior |
| Wallpaper | blue-brick halls `(1,0)` | same as Mosaic when the figure is underground |
| Interior1 | `(1,0)` is common black fill, not a figure; desks/ladders count ≥20. Node z=0, behind Nina | rare overlay on the body |
| Interior2 | yellow crates only (z=10, in front of Nina, behind Foreground). No collision | do not put desks, signs, or baked figures here |
| Structure | red brick floor `(1,0)` only | rare non-floor tiles (count 1–2) on the silhouette — **erase**, do not fill |

Nina (`Z_ACTORS` = 8) walks between them: Interior1 behind her, Interior2 in front,
Foreground (12) in front of both. Crate body tiles plus the `04` plate in
`chunk_00_02` are on Interior2. A figure standing in the gap between two crates
stays on Interior1. `blit_scan.parse_chunk` merges both nodes back into
`"Interior"` for the scanners.

Dump **both** Interior and Mosaic/Wallpaper per cell (`i=` and `m=`). An
Interior-first grid hides empty mosaic under furniture.

Skip Interior `(1,0)` and any Interior atlas used ≥20 times (ladders, desks,
cabinets). Never fill empty mosaic/structure rows that are the red floor gap.

## Find a baked figure

Run `python .mcp/screenshots/scan_figures.py` (optional blit:
`python .mcp/screenshots/blit_scan.py`). Do not rely on a handful of
standing keys — that sweep missed HQ furniture composites, mosaic
rider+panther, 6-wide wallpaper standing, and wallpaper-hall panthers.

1. Confirm `get_edited_scene_root().scene_file_path` is the target chunk.
2. Count atlas coords. Rare Mosaic/Wallpaper (not fill / not 2,0 / 3,0),
   rare Interior (not 1,0, count < 20), rare Structure (not 1,0).
3. Cluster **Interior + Mosaic + Wallpaper together**. Interior overlay
   punches holes in wallpaper/mosaic, so a layer-only blob splits.
4. Shapes: standing 2–7 × 6–8 (wallpaper halls are often 6 wide).
   Panther 3–12 × 2–5. Rider+panther ~5–12 × 6–8. Isolated mosaic `(17,0)` / `(17,1)` is a
   desk/door false positive, not a figure.
5. Confirm visually before mutating. Do not erase furniture, ladders, or a
   panther unless asked. The fan map's magenta `?NN` code signs (14 of them,
   `02` included) are already erased: `.mcp/screenshots/qmark_erase.py`
   refills each sign cell from a clean neighbour and restores hidden crate
   cells by hand. The small yellow box under each sign is a prop — keep it.

Known pose keys live in `.mcp/screenshots/scan_figures.py` (`POSES`):
HQ cabinet-guard / desk-panther / bookcase-guard, HQ mosaic-wall panther,
HQ hill rider, wallpaper-hall standing, wallpaper-hall panther, cave-edge
panther (blue brick by a ladder), walking A/B, dark-hall, sky standing,
blue-brick standing. Add a new pose there when a figure is found by eye.

Shape clusters run only around a pose hit (cabinets are 5×8 and desks
are 6×4). Isolated mosaic `(17,0)` / `(17,1)` and singleton walk mosaic
are filtered as scenery.

## Furniture (desks, cabinets)

Furniture Interior tiles are often **transparent**. Filling mosaic `(1,0)`
under them makes green wallpaper show through the desk. That is a broken
edit; roll back and retry.

A clean 6-wide HQ desk (Interior empty mosaic except cavity/feet):

```
y+0 wallpaper:  m(1,0) ×6
y+1 openings:   m(1,0) m(1,0) i(25,1) i(21,1) m(1,0) m(1,0)
y+2 top:        i(22,1) i(23,1) i(28,0) i(28,0) i(20,1) i(19,1)   mosaic empty
y+3 mid:        i(0,1)  i(4,1)  i(24,1) i(26,1) i(1,1)  i(31,0)   mosaic empty
y+4 cavity:     i(0,1)  i(4,1)  m(8,0)  m(10,0) i(1,1)  i(31,0)
y+5 feet:       m(5,0)  m(1,0)  m(7,0)  m(9,0)  m(1,0)  m(6,0)
```

A 5-wide cyan cabinet is Interior-only (`11,2` / `30,1` / `13,2` / … / `14,2`)
with mosaic empty under it and wallpaper `(1,0)` beside it.

A 7-wide HQ bookcase (Interior books + mosaic chrome `12,0`/`13,0`/`15,0`/`11,0`/`16,0`,
mosaic empty under books; Structure `(6,0)` on a few shelf cells). Clone the twin
bbox (dx 0–6, dy 0–8). Do not copy the floor row under the case — `(3,0)` stripes
and Interior `(1,0)` black sit there. Mosaic `(20,0)`/`(22,0)` on the feet are
figure leftovers, not chrome.

When a figure overlaps a prop:

1. Find a **clean twin** of the same prop on this chunk (same atlas pattern,
   different origin).
2. Restore Interior atlas on overlapped cells from the twin.
3. Keep mosaic **empty** under those Interior cells. Never paint `(1,0)` there.
4. Fill wallpaper `(1,0)` only on cells that are wallpaper on the twin
   (silhouette beside/above the prop, mosaic holes behind the standing body).
5. Restore mosaic cavity/feet from the twin (`8,0`/`10,0`, `5,0`/`6,0`/`7,0`/`9,0`)
   — those are not wallpaper.
6. Diff the prop bbox against the twin. It must match, including `m=-`
   under Interior.

## Lift baked legs out of Mosaic

Symptom the user reports: "стол развалился на 2 слоя" — the desk body sits on
Interior while its legs and the chair post sit on Mosaic and blend into the
wall. The rip baked those ZX characters as *wall + leg* composites, so the leg
is not a separate tile anywhere; `punch_wallpaper` in
`tools/saboteur_rip/decompose_world.py` never saw them as part of the prop.

Mosaic `(5,0)` `(6,0)` `(7,0)` `(8,0)` `(9,0)` `(10,0)` are those composites:
`(8,0)`/`(10,0)` the chair post row, the rest desk feet. They are the same
cells the "Furniture" section calls cavity/feet.

Split pixels, do not move the tile: **a column that is black in all 8 rows is
the leg**; everything else in the tile is wallpaper. In chunk_02_01 that gave
four distinct overlays — `(5,0)`→cols 1-3, `(6,0)`→cols 4-6, `(7,0)`/`(8,0)`
→col 7, `(9,0)`/`(10,0)`→col 0.

1. Find free Interior atlas slots: fully transparent **and** unused by any
   `chunk_*.tscn`. The tail of the atlas has them (`(25,30)`…`(31,30)`);
   leave `(0,0)` alone. `s2_interior_tileset.tres` already declares all
   32×31 slots, so only the PNG changes — no `.tres` edit, no atlas resize.
2. Paint the leg columns (opaque black, rest transparent) into those slots in
   `assets/tilesets/s2_interior_tileset.png` **before** restarting the editor,
   so the import picks them up. Refuse to write a slot that is not empty.
3. Per cell: `Interior.set_cell(cell, 0, slot)` and `Mosaic.set_cell(cell, 0,
   (1,0))`. This is the one case where filling mosaic under Interior is right
   — the Interior tile is a transparent overlay, not opaque furniture.
4. The wall behind the leg changes by 5–13 px per cell: the ZX composite
   clipped the wallpaper square, the plain `(1,0)` square is not clipped.
   Render a before/after blit and show it before committing.
5. Verify from the saved `.tscn`: no Mosaic cell keeps a leg atlas, and every
   moved cell reads `interior=<slot>, mosaic=(1,0)`.

Then fill the wall behind the prop when asked ("заполни обоями стену за
столом"): the rip leaves Mosaic **empty** under the whole desk footprint, so
the wall layer has a prop-shaped hole. Fill those cells with `(1,0)` too.
This is the exception to "never paint mosaic under Interior" — check it, do
not assume: read the Interior tile out of the atlas and refuse the fill if
any pixel has `a < 1.0`. HQ desk/chair tiles are fully opaque with the wall
baked in, so the fill is invisible today and correct the day those tiles get
their background punched out. Transparent furniture (see the Furniture
section) still keeps mosaic empty.

The standalone desk is the 6-wide cyan one. Match it on Interior before
touching anything: top row `(22,1) (23,1) (28,0) (28,0) (20,1) (19,1)`, the
row under it `(0,1) (4,1) (24,1) (26,1) (1,1) (31,0)`, side cells of the next
row `(0,1) (4,1)` … `(1,1) (31,0)`. The footprint to fill is that origin
shifted up one row (the red chair back) and down through the feet, 6×5.
Yellow cabinet rows are a different prop: they only bake the outer feet
`(5,0)`/`(6,0)` and do not match this signature — leave them. Mosaic
`(17,0)` on a desk is near-wallpaper (2 px off), not a leg; leave it.

Done once, across every chunk that has this desk (124 desks, 14 chunks:
`01_03`, `02_01`–`02_04`, `03_00`–`03_04`, `04_02`, `04_03`, `05_02`,
`06_02`). Leg slots are the four tiles above. Two desks in `chunk_01_03`
(`(105,65)`, `(116,65)`) keep `(17,0)` where the chair post was.

`build_world_atlas.py`, `build_tilesets.py` and `slice_world_tiles.py` write
`draft/` and leave `assets/tilesets` alone. `--overwrite` is what replaces
the appended tiles.

## Erase a figure

Per cell, decide from the twin (or from empty wallpaper), then:

- Interior overlay that is **not** furniture → `set_cell(cell, -1)`.
- Furniture Interior that was composited with the figure → set the twin atlas,
  mosaic stays empty.
- Mosaic/Wallpaper unique tiles and holes that are wallpaper on the twin →
  fill `(1,0)` (Wallpaper halls: Wallpaper layer, not Mosaic).
- Structure non-`(1,0)` on the silhouette → erase (`-1`). Do not fill Structure.
- Never fill Mosaic `(2,0)`/`(3,0)` panel stripes.

Wrap in editor undo, then save:

```
var ur := EditorInterface.get_editor_undo_redo()
ur.create_action("Erase baked guard")
# do/undo via layer.set_cell(cell, src, atlas, alt)
# erase: src=-1, atlas=(-1,-1)
ur.commit_action()
EditorInterface.save_scene()
```

Verify: blit the bbox; twin-diff the furniture; Structure has no non-floor
tiles left on the silhouette.

## Examples

`chunk_02_04` — Mosaic wallpaper halls. Two standing guards `(42,5)–(44,11)`
and `(15,23)–(17,29)`. One HQ desk at `(52,46)–(57,50)`: 6 legs lifted onto
Interior, 18 footprint cells filled with wallpaper.

`chunk_02_06` — blue hall: same recipe on **Wallpaper** `(1,0)`, not Mosaic.

`chunk_02_01` — two standalone desks (`(25,30)`, `(119,67)`) plus a yellow
cabinet row at `x 17-22`. Cabinet feet stayed on Mosaic.

`chunk_03_02` — HQ with desks/cabinets. Standing guards on Mosaic+Interior;
one also left Structure `(20,0)`/`(24,0)` on the desk — erase those. Restore
desk/cabinet from a twin; do not fill mosaic under Interior. Leave the panther
unless asked.
