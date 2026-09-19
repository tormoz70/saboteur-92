extends LevelBase

## Saboteur II world map. Tile layers come from the prebuilt chunk scenes in
## scenes/world/chunks/; everything else (camera, spawn, ladders, entities,
## ink outline) lives in LevelBase.

const CHUNKS_MANIFEST_PATH := "res://scenes/world/chunks/chunks.json"
const ENTITIES_PATH := "res://assets/world/s2_entities.json"
const COLLISION_PATH := "res://assets/world/s2_collision.json"

@onready var world_map: Node2D = $WorldMap


func _entities_path() -> String:
	return ENTITIES_PATH


func _collision_data_path() -> String:
	return COLLISION_PATH


func _setup_layers() -> bool:
	return _setup_from_chunks()


func _collision_sources() -> Array:
	var sources: Array = []
	if world_map == null:
		return sources
	for chunk_node in world_map.get_children():
		var chunk := chunk_node as Node2D
		if chunk == null:
			continue
		var collision := chunk.get_node_or_null("CollisionLayer") as TileMapLayer
		if collision:
			sources.append([collision, chunk.position])
	return sources


func _setup_from_chunks() -> bool:
	var manifest := _load_json(CHUNKS_MANIFEST_PATH, false)
	if manifest.is_empty():
		push_error("Missing %s — world chunks have not been generated yet" % CHUNKS_MANIFEST_PATH)
		return false
	_scale = float(manifest.get("scale", _scale))
	var sz: Array = manifest.get("size", [_world_size.x, _world_size.y])
	_world_size = Vector2(float(sz[0]), float(sz[1]))
	var scr: Array = manifest.get("screen", [_screen.x, _screen.y])
	_screen = Vector2(float(scr[0]), float(scr[1]))
	_setup_sky_fill(manifest)

	var chunk_cells: Array = manifest.get("chunk_cells", [128, 72])
	var cell := int(manifest.get("cell", 8))
	var chunks_x := int(manifest.get("chunks_x", 1))
	var paths: Array = manifest.get("paths", [])
	var origin := Vector2(float(chunk_cells[0]) * cell, float(chunk_cells[1]) * cell)

	_map_layers.clear()
	for i in paths.size():
		var packed: PackedScene = load(str(paths[i]))
		if packed == null:
			continue
		var chunk := packed.instantiate() as Node2D
		if chunk == null:
			continue
		var gx := i % chunks_x
		var gy := i / chunks_x
		chunk.position = Vector2(gx, gy) * origin
		world_map.add_child(chunk)
		for child in chunk.get_children():
			if child is TileMapLayer:
				_register_layer(child)
	if sky_fill:
		_map_layers["sky"] = sky_fill
	_map_layers["artifacts"] = artifacts_layer
	_map_layers["machines"] = machines_layer
	_map_layers["actors"] = actors_layer
	return true
