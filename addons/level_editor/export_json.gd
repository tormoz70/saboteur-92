@tool
class_name LevelJsonExport
extends RefCounted

const TILES_PATH := "res://assets/world/s2_world_tiles.json"
const COLLISION_TILES_PATH := "res://assets/world/s2_collision_tiles.json"
const COLLISION_PATH := "res://assets/world/s2_collision.json"

const LAYER_NODES := {
	"sky": "Sky",
	"earth": "Earth",
	"structure": "Structure",
	"wallpaper": "Wallpaper",
	"interior": "Interior",
	"fg": "Foreground",
}


func export_from_level(level: Node) -> Dictionary:
	var tiles := _load_json(TILES_PATH)
	if tiles.is_empty():
		return {}
	var grid: Array = tiles.get("grid", [0, 0])
	var cw := int(grid[0])
	var ch := int(grid[1])
	var layers: Dictionary = tiles.get("layers", {})
	for key in LAYER_NODES:
		var node := level.get_node_or_null(LAYER_NODES[key]) as TileMapLayer
		var spec: Dictionary = layers.get(key, {})
		if node == null or spec.is_empty():
			continue
		var empty_id := int(spec.get("empty", 0))
		var atlas: Array = spec.get("atlas_tiles", [1, 1])
		var cols := int(atlas[0])
		spec["rle"] = _layer_rle(node, cw, ch, cols, empty_id)
		layers[key] = spec
	tiles["layers"] = layers
	var collision := _load_json(COLLISION_TILES_PATH)
	var clayer := level.get_node_or_null("CollisionLayer") as TileMapLayer
	if clayer and not collision.is_empty():
		collision["rle"] = _collision_rle(clayer, cw, ch)
		collision["ladder_rle"] = _ladder_rle_from_layer(clayer, cw, ch, collision)
		_write_json(COLLISION_TILES_PATH, collision)
		_refresh_rect_json(collision)
	_write_json(TILES_PATH, tiles)
	return {"tiles": tiles, "collision": collision}


func import_into_level(level: Node) -> void:
	var tiles := _load_json(TILES_PATH)
	var specs: Dictionary = tiles.get("layers", {})
	for key in LAYER_NODES:
		var node := level.get_node_or_null(LAYER_NODES[key]) as TileMapLayer
		var spec: Dictionary = specs.get(key, {})
		if node == null or spec.is_empty():
			continue
		var fill_spec := spec.duplicate()
		fill_spec["grid"] = tiles.get("grid", [])
		TileMapUtils.fill_from_rle(node, fill_spec)
	var collision := _load_json(COLLISION_TILES_PATH)
	var clayer := level.get_node_or_null("CollisionLayer") as TileMapLayer
	if clayer and not collision.is_empty():
		TileMapUtils.fill_from_rle(clayer, collision)


func rle_matches(a: Array, b: Array) -> bool:
	return a.hash() == b.hash() and a == b


func _layer_rle(
	layer: TileMapLayer, cw: int, ch: int, atlas_cols: int, empty_id: int
) -> Array:
	var ids := PackedInt32Array()
	ids.resize(cw * ch)
	for i in ids.size():
		ids[i] = empty_id
	for cell in layer.get_used_cells():
		if cell.x < 0 or cell.y < 0 or cell.x >= cw or cell.y >= ch:
			continue
		var atlas := layer.get_cell_atlas_coords(cell)
		ids[cell.y * cw + cell.x] = atlas.y * atlas_cols + atlas.x
	return TileMapUtils.rle_encode(ids)


func _collision_rle(layer: TileMapLayer, cw: int, ch: int) -> Array:
	var ids := PackedInt32Array()
	ids.resize(cw * ch)
	for cell in layer.get_used_cells():
		if cell.x < 0 or cell.y < 0 or cell.x >= cw or cell.y >= ch:
			continue
		var atlas := layer.get_cell_atlas_coords(cell)
		var tid := atlas.x
		if tid < 0:
			tid = 0
		ids[cell.y * cw + cell.x] = tid
	return TileMapUtils.rle_encode(ids)


func _ladder_rle_from_layer(
	layer: TileMapLayer, cw: int, ch: int, collision: Dictionary
) -> Array:
	var previous := TileMapUtils.rle_decode(collision.get("ladder_rle", []))
	var ids := PackedInt32Array()
	ids.resize(cw * ch)
	for i in ids.size():
		var prev := 0
		if i < previous.size():
			prev = previous[i]
		ids[i] = prev
	for cell in layer.get_used_cells():
		if cell.x < 0 or cell.y < 0 or cell.x >= cw or cell.y >= ch:
			continue
		var kind := TileMapUtils.get_collision_type(layer, cell)
		var i := cell.y * cw + cell.x
		if kind == "ladder":
			ids[i] = 1
		elif kind == "empty":
			ids[i] = 0
		# solid/oneway keep previous climb bit so hatch lids survive
	return TileMapUtils.rle_encode(ids)


func _refresh_rect_json(collision: Dictionary) -> void:
	var rects := _load_json(COLLISION_PATH)
	if rects.is_empty():
		return
	var grid: Array = collision.get("grid", [])
	if grid.size() < 2:
		return
	var cw := int(grid[0])
	var ch := int(grid[1])
	var cell := int(collision.get("cell", TileMapUtils.CELL))
	var ids := TileMapUtils.rle_decode(collision.get("rle", []))
	var climb := TileMapUtils.rle_decode(collision.get("ladder_rle", []))
	var masks := TileMapUtils.ids_to_masks(ids, cw, ch, climb)
	rects["solids"] = TileMapUtils.greedy_merge_rects(masks["solid"], cell)
	rects["ladders"] = TileMapUtils.ladder_rects(masks["climb"], cell)
	_write_json(COLLISION_PATH, rects)


func _load_json(path: String) -> Dictionary:
	if not FileAccess.file_exists(path):
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		return {}
	return parsed


func _write_json(path: String, data: Dictionary) -> void:
	var abs_path := ProjectSettings.globalize_path(path)
	var file := FileAccess.open(abs_path, FileAccess.WRITE)
	if file == null:
		push_error("Cannot write %s" % path)
		return
	file.store_string(JSON.stringify(data))
