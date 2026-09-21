@tool
extends SceneTree

## Build native chunk scenes from the lossless cell grid.
##
## Run headless from the repo root:
##   tools/godot/Godot_v4.6-stable_win64_console.exe --headless --path . --script tools/build_world_chunks.gd
##
## Reads  assets/world/s2_world_cells.json  (1024x576 grid of [layer, tile_id])
## Writes scenes/world/chunks/chunk_XX_YY.tscn  (64 chunks of 128x72 cells)
## plus   scenes/world/chunks/chunks.tres     (manifest for the runtime)

const CELLS_PATH := "res://assets/world/s2_world_cells.json"
const COLLISION_GRID_PATH := "res://assets/world/s2_collision_grid.json"
const CHUNK_DIR := "res://scenes/world/chunks"
const MANIFEST_PATH := "res://scenes/world/chunks/chunks.json"

const CELL := 8
const CHUNK_CW := 128
const CHUNK_CH := 72

# Layer name -> scene node name. Order matches s2_world_cells.json "layers".
const LAYER_NODES := {
	"earth": "Earth",
	"structure": "Structure",
	"wallpaper": "Wallpaper",
	"mosaic": "Mosaic",
	# Hand-edited chunks call this node Interior1 and put yellow crates on
	# Interior2 (z=10, in front of Nina). Rebuilding flattens that split.
	"interior": "Interior",
	"fg": "Foreground",
}


func _init() -> void:
	var cells := _load_cells()
	if cells.is_empty():
		push_error("Missing %s — run build_world_atlas.py first" % CELLS_PATH)
		quit(1)
		return
	var grid: Array = cells.get("grid", [])
	var cw := int(grid[0])
	var ch := int(grid[1])
	var layers: Array = cells.get("layers", [])
	var tilesets := _load_tilesets(layers)
	var collision := _load_collision_grid(cw, ch)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(CHUNK_DIR))
	var chunk_paths: Array[String] = []
	var chunks_x := cw / CHUNK_CW
	var chunks_y := ch / CHUNK_CH
	for gy in chunks_y:
		for gx in chunks_x:
			var path := "%s/chunk_%02d_%02d.tscn" % [CHUNK_DIR, gx, gy]
			_build_chunk(cells, gx, gy, tilesets, collision, path)
			chunk_paths.append(path)
	_write_manifest(chunk_paths, chunks_x, chunks_y, cells)
	print("build_world_chunks: wrote %d chunks to %s" % [chunk_paths.size(), CHUNK_DIR])
	quit(0)


func _load_cells() -> Dictionary:
	if not FileAccess.file_exists(CELLS_PATH):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(CELLS_PATH))
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


func _load_tilesets(layers: Array) -> Array:
	var out: Array = []
	for layer in layers:
		var name := str(layer.get("name", ""))
		var tres := "res://assets/tilesets/s2_%s_tileset.tres" % name
		var ts: TileSet = null
		if ResourceLoader.exists(tres):
			ts = load(tres)
		out.append(ts)
	return out


func _load_collision_grid(cw: int, ch: int) -> Array:
	# Per-cell collision_type ids (0 empty, 1 solid, 2 ladder, 3 oneway).
	# Empty when build_collision.py has not run yet — chunks then build with an
	# empty CollisionLayer.
	if not FileAccess.file_exists(COLLISION_GRID_PATH):
		return []
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(COLLISION_GRID_PATH))
	if typeof(parsed) != TYPE_DICTIONARY:
		return []
	var ids: Array = parsed.get("cells", [])
	if ids.size() != cw * ch:
		push_warning("collision grid size mismatch; ignoring")
		return []
	return ids


func _build_chunk(
	cells: Dictionary, gx: int, gy: int, tilesets: Array, collision: Array, path: String
) -> void:
	var grid: Array = cells.get("grid", [])
	var cw := int(grid[0])
	var data: Array = cells.get("cells", [])
	var layers: Array = cells.get("layers", [])

	var root := Node2D.new()
	root.name = "Chunk_%02d_%02d" % [gx, gy]

	# Visual layers.
	var layer_nodes: Array[TileMapLayer] = []
	for li in layers.size():
		var layer: Dictionary = layers[li]
		var name := str(layer.get("name", ""))
		var node := TileMapLayer.new()
		node.name = LAYER_NODES.get(name, name.capitalize())
		node.z_index = int(layer.get("z", 0))
		node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
		if tilesets[li] != null:
			node.tile_set = tilesets[li]
		root.add_child(node)
		node.owner = root
		layer_nodes.append(node)

	# Collision layer, stamped from the collision grid when present.
	var collision_node := TileMapLayer.new()
	collision_node.name = "CollisionLayer"
	collision_node.visible = false
	collision_node.z_index = 20
	collision_node.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	var ctres := "res://assets/tilesets/s2_collision_tileset.tres"
	if ResourceLoader.exists(ctres):
		collision_node.tile_set = load(ctres)
	root.add_child(collision_node)
	collision_node.owner = root

	# Fill cells.
	var x0 := gx * CHUNK_CW
	var y0 := gy * CHUNK_CH
	var has_collision := not collision.is_empty() and collision_node.tile_set != null
	for y in CHUNK_CH:
		for x in CHUNK_CW:
			var src: Array = data[(y0 + y) * cw + (x0 + x)]
			var li := int(src[0])
			if li >= 0:
				var tid := int(src[1])
				var node: TileMapLayer = layer_nodes[li]
				if node.tile_set != null:
					var source := node.tile_set.get_source(0) as TileSetAtlasSource
					if source != null:
						# Pack order is tile_id in a grid of PNG_width/8, not
						# Godot's padded atlas-grid size (stale .tres used to
						# report 31 rows for a 32-row interior atlas).
						var cols: int = CELL
						if source.texture != null:
							cols = maxi(1, source.texture.get_width() / CELL)
						node.set_cell(Vector2i(x, y), 0, Vector2i(tid % cols, tid / cols))
			if has_collision:
				var ctype := int(collision[(y0 + y) * cw + (x0 + x)])
				if ctype != 0:
					collision_node.set_cell(Vector2i(x, y), 0, Vector2i(ctype, 0))

	var packed := PackedScene.new()
	var err := packed.pack(root)
	if err != OK:
		push_error("pack failed for %s: %s" % [path, error_string(err)])
		return
	ResourceSaver.save(packed, path)


func _write_manifest(
	chunk_paths: Array[String], chunks_x: int, chunks_y: int, cells: Dictionary
) -> void:
	var doc := {
		"chunks_x": chunks_x,
		"chunks_y": chunks_y,
		"chunk_cells": [CHUNK_CW, CHUNK_CH],
		"cell": CELL,
		"scale": cells.get("scale", 2),
		"screen": cells.get("screen", [256, 192]),
		"size": cells.get("size", [8192, 4608]),
		"sky_color": cells.get("sky_color", [0, 0, 206]),
		"paths": chunk_paths,
	}
	var file := FileAccess.open(ProjectSettings.globalize_path(MANIFEST_PATH), FileAccess.WRITE)
	if file:
		file.store_string(JSON.stringify(doc, "  "))
		file.close()
