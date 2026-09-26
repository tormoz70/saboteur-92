class_name WorldBuilder
extends RefCounted

## Runtime *JSON -> Godot* half of the two-way chunk bridge (see
## tools/export_chunks_to_json.py for the reverse). Reconstructs a chunk
## Node2D — its TileMapLayers and entities — from a Dictionary matching
## docs/world_chunk_schema.json, resolving simple integer palette ids back to
## real TileSet atlas coordinates via a data-driven id map.
##
## Nothing here is hardcoded to a specific TileSet: layer -> TileSet and
## palette-id -> atlas mappings all come from tile_id_map.json, so an AI (or a
## human) can author new chunks purely as integer grids.
##
## Typical use:
##     var root := WorldBuilder.build_from_file(
##         "res://assets/world/chunks_json/chunk_03_03.json")
##     add_child(root)
##
## or, when you already hold a parsed dictionary (e.g. straight from an LLM):
##     var root := WorldBuilder.new().build(chunk_dict)

const DEFAULT_ID_MAP := "res://assets/tilesets/tile_id_map.json"
const TEXTURE_FILTER_NEAREST := 1  # CanvasItem.TEXTURE_FILTER_NEAREST

## Cache so repeated builds don't reload the same .tres / id map from disk.
var _id_map: Dictionary = {}
var _tileset_cache: Dictionary = {}
var _scene_cache: Dictionary = {}


## Build a chunk from a file path (chunk JSON). Convenience wrapper.
static func build_from_file(json_path: String, id_map_override: Dictionary = {}) -> Node2D:
	if not FileAccess.file_exists(json_path):
		push_error("WorldBuilder: chunk file not found: %s" % json_path)
		return null
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(json_path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("WorldBuilder: could not parse chunk JSON: %s" % json_path)
		return null
	return WorldBuilder.new().build(parsed, id_map_override)


## Build and return the chunk root Node2D, ready to add to the SceneTree.
## `id_map_override` lets callers inject a map (tests, in-memory pipelines);
## otherwise it is loaded from chunk_data.tile_id_map (or DEFAULT_ID_MAP).
func build(chunk_data: Dictionary, id_map_override: Dictionary = {}) -> Node2D:
	_id_map = id_map_override if not id_map_override.is_empty() else _load_id_map(chunk_data)
	if _id_map.is_empty():
		push_error("WorldBuilder: no id map available; cannot resolve tiles")
		return null

	var cell_size := int(chunk_data.get("cell_size", _id_map.get("cell_size", 8)))
	var grid_size: Array = chunk_data.get("grid_size", _id_map.get("grid_size", [128, 72]))
	var width := int(grid_size[0])
	var height := int(grid_size[1])
	var empty_id := int(chunk_data.get("empty_id", _id_map.get("empty_id", -1)))

	var root := Node2D.new()
	root.name = str(chunk_data.get("chunk_id", "Chunk"))

	_build_layers(root, chunk_data, width, height, empty_id)
	_spawn_entities(root, chunk_data, cell_size)
	return root


# --- Terrain / decoration layers -------------------------------------------

func _build_layers(root: Node2D, chunk_data: Dictionary, width: int, height: int,
		empty_id: int) -> void:
	var layers_cfg: Dictionary = _id_map.get("layers", {})
	var palettes: Dictionary = _id_map.get("palettes", {})
	var chunk_layers: Dictionary = chunk_data.get("layers", {})
	# layer_order guarantees deterministic z-ordering / node order.
	var order: Array = _id_map.get("layer_order", layers_cfg.keys())

	for key in order:
		var cfg: Dictionary = layers_cfg.get(key, {})
		if cfg.is_empty():
			continue
		var layer := TileMapLayer.new()
		layer.name = str(cfg.get("node_name", key))
		layer.z_index = int(cfg.get("z_index", 0))
		layer.visible = bool(cfg.get("visible", true))
		layer.texture_filter = TEXTURE_FILTER_NEAREST
		layer.tile_set = _get_tileset(str(cfg.get("tileset", "")))
		root.add_child(layer)

		# A layer absent from this chunk (or empty) stays an empty TileMapLayer.
		if not chunk_layers.has(key):
			continue
		var palette: Array = palettes.get(str(cfg.get("palette", "")), {}).get("tiles", [])
		_fill_layer(layer, chunk_layers[key], palette, width, height, empty_id)


## Populate one TileMapLayer from a schema layer entry using set_cell().
## For bulk rebuilds you could instead assemble a PackedByteArray and assign
## layer.tile_map_data directly (see scripts/world/tilemap_utils.gd) — that is
## faster but less legible; set_cell keeps the mapping explicit and robust.
func _fill_layer(layer: TileMapLayer, layer_data: Dictionary, palette: Array,
		width: int, height: int, empty_id: int) -> void:
	var flat := _decode_layer(layer_data, width, height, empty_id)
	if flat.is_empty():
		return
	for y in height:
		var row_base := y * width
		for x in width:
			var pid := flat[row_base + x]
			if pid == empty_id or pid < 0 or pid >= palette.size():
				continue
			var tile: Array = palette[pid]
			# tile = [source_id, atlas_x, atlas_y, alternative_tile]
			layer.set_cell(
				Vector2i(x, y),
				int(tile[0]),
				Vector2i(int(tile[1]), int(tile[2])),
				int(tile[3])
			)


## Return a flat PackedInt32Array of palette ids (row-major, length w*h),
## decoding either the dense "grid" or compact "rle" encoding.
func _decode_layer(layer_data: Dictionary, width: int, height: int,
		empty_id: int) -> PackedInt32Array:
	var encoding := str(layer_data.get("encoding", "grid"))
	var data: Array = layer_data.get("data", [])
	var out := PackedInt32Array()
	if encoding == "rle":
		out.resize(width * height)
		out.fill(empty_id)
		var i := 0
		var pos := 0
		while i + 1 < data.size():
			var value := int(data[i])
			var count := int(data[i + 1])
			for _n in count:
				if pos >= out.size():
					break
				out[pos] = value
				pos += 1
			i += 2
		return out
	# dense grid: array of rows
	out.resize(width * height)
	out.fill(empty_id)
	for y in mini(height, data.size()):
		var row: Array = data[y]
		for x in mini(width, row.size()):
			out[y * width + x] = int(row[x])
	return out


# --- Entities ---------------------------------------------------------------

func _spawn_entities(root: Node2D, chunk_data: Dictionary, cell_size: int) -> void:
	var entities: Array = chunk_data.get("entities", [])
	if entities.is_empty():
		return
	var prefabs: Dictionary = _id_map.get("entity_prefabs", {})
	var holder := Node2D.new()
	holder.name = "Entities"
	root.add_child(holder)

	for spec in entities:
		if typeof(spec) != TYPE_DICTIONARY:
			continue
		var etype := str(spec.get("type", ""))
		var scene_path := str(prefabs.get(etype, ""))
		var pos_cells: Array = spec.get("position", [0, 0])
		var pos_px := Vector2(float(pos_cells[0]), float(pos_cells[1])) * float(cell_size)

		var node: Node2D
		if scene_path != "" and ResourceLoader.exists(scene_path):
			node = _get_scene(scene_path).instantiate() as Node2D
		else:
			# Unknown/marker type: drop a Marker2D so the position survives and
			# nothing crashes. Lets AI reference types the game doesn't yet have.
			if scene_path != "":
				push_warning("WorldBuilder: no prefab for entity '%s'" % etype)
			node = Marker2D.new()
		if node == null:
			continue
		node.name = str(spec.get("id", etype)).capitalize()
		node.position = pos_px
		_apply_params(node, spec.get("params", {}))
		holder.add_child(node)


## Best-effort parameter application: call a `setup(params)` method if the
## prefab defines one, otherwise set any matching exported/script properties.
func _apply_params(node: Node, params: Dictionary) -> void:
	if params.is_empty():
		return
	if node.has_method("setup"):
		node.callv("setup", [params])
		return
	var prop_names := {}
	for p in node.get_property_list():
		prop_names[p.name] = true
	for k in params:
		if prop_names.has(k):
			node.set(k, params[k])


# --- Resource helpers (cached) ---------------------------------------------

func _load_id_map(chunk_data: Dictionary) -> Dictionary:
	var path := str(chunk_data.get("tile_id_map", DEFAULT_ID_MAP))
	if not FileAccess.file_exists(path):
		push_error("WorldBuilder: id map not found: %s" % path)
		return {}
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("WorldBuilder: could not parse id map: %s" % path)
		return {}
	return parsed


func _get_tileset(path: String) -> TileSet:
	if path == "":
		return null
	if _tileset_cache.has(path):
		return _tileset_cache[path]
	var ts: TileSet = null
	if ResourceLoader.exists(path):
		ts = load(path) as TileSet
	if ts == null:
		push_warning("WorldBuilder: could not load TileSet %s" % path)
	_tileset_cache[path] = ts
	return ts


func _get_scene(path: String) -> PackedScene:
	if _scene_cache.has(path):
		return _scene_cache[path]
	var ps := load(path) as PackedScene
	_scene_cache[path] = ps
	return ps
