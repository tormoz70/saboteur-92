---
name: edit-world-chunks
description: >-
  Observe and edit Saboteur II world chunk TileMaps through Godot MCP.
  Finds and erases baked ZX figures (guards, panthers) split across Mosaic,
  Wallpaper, Interior, and Structure; restores wallpaper and furniture from a
  clean twin; saves with editor undo. Use when the user edits chunks, paints
  TileMap, asks to watch Godot, or to remove baked guards/sprites from mosaic,
  wallpaper, interior, or structure layers.
---

# Edit world chunks via Godot MCP

Map lives in `scenes/world/chunks/chunk_XX_YY.tscn` (128×72 cells, 8 px).
Do not rebuild chunks with `tools/build_world_chunks.gd` after a hand edit.

## MCP session

Namespace: `project-0-saboteur-92-godot` (`godot-mcp-runtime`).

1. If tools are missing: Customize → MCP → enable **godot**.
2. Godot editor must already be open on this project. The editor plugin
   `addons/mcp_bridge` listens on `127.0.0.1:35676`.
3. `attach_project` with `projectPath` = repo root and `bridgePort` = 35676.
4. If attach writes `McpBridge=...` into `project.godot`, **revert that line**.
   The editor plugin already hosts the bridge; a second autoload is wrong.
5. `take_screenshot` times out in the editor. Capture via `run_script` instead.

`run_script` must `extends RefCounted` and define
`func execute(scene_tree: SceneTree) -> Variant`.

Do not call `Engine.get_singleton` (blocked). Use `EditorInterface` by name.

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
| Interior | `(1,0)` is common black fill, not a figure; desks/ladders count ≥20 | rare overlay on the body |
| Structure | red brick floor `(1,0)` only | rare non-floor tiles (count 1–2) on the silhouette — **erase**, do not fill |

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
   Panther 3–12 × 2–5. Rider+panther ~5–12 × 6–8. Magenta `02` signs
   are props — leave them. Isolated mosaic `(17,0)` / `(17,1)` is a
   desk/door false positive, not a figure.
5. Confirm visually before mutating. Do not erase `?` marks, furniture,
   ladders, or a panther unless asked.

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

`chunk_02_04` — Mosaic wallpaper only, no furniture. Two standing guards
`(42,5)–(44,11)` and `(15,23)–(17,29)`.

`chunk_02_06` — blue hall: same recipe on **Wallpaper** `(1,0)`, not Mosaic.

`chunk_03_02` — HQ with desks/cabinets. Standing guards on Mosaic+Interior;
one also left Structure `(20,0)`/`(24,0)` on the desk — erase those. Restore
desk/cabinet from a twin; do not fill mosaic under Interior. Leave the panther
and the magenta `02` sign unless asked.
