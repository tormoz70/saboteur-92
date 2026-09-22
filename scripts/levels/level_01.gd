extends LevelBase

## Saboteur II world map. Tile layers come from the prebuilt chunk scenes in
## scenes/world/chunks/; everything else (camera, spawn, ladders, entities,
## ink outline) lives in LevelBase.

const CHUNKS_MANIFEST_PATH := "res://scenes/world/chunks/chunks.json"
const ENTITIES_PATH := "res://assets/world/s2_entities.json"
const COLLISION_PATH := "res://assets/world/s2_collision.json"
const CHUNKS_PER_FRAME := 4

@onready var world_map: Node2D = $WorldMap


func _entities_path() -> String:
	return ENTITIES_PATH


func _collision_data_path() -> String:
	return COLLISION_PATH


func _setup_layers() -> bool:
	return _setup_from_chunks()


## Loads and adds the chunk scenes a few per frame.
## Built in a single frame the map blocked the main loop for ~7 s, longer
## than the MCP bridge handshake waits.
func _load_world() -> void:
	await get_tree().process_frame
	var manifest := _load_json(CHUNKS_MANIFEST_PATH, false)
	if manifest.is_empty():
		return
	var chunk_cells: Array = manifest.get("chunk_cells", [128, 72])
	var cell := int(manifest.get("cell", 8))
	var chunks_x := int(manifest.get("chunks_x", 1))
	var paths: Array = manifest.get("paths", [])
	var origin := Vector2(float(chunk_cells[0]) * cell, float(chunk_cells[1]) * cell)

	# Not ResourceLoader.load_threaded_request: parallel chunk loads left an
	# atlas image empty and crashed the engine after other scenes had run.
	for i in paths.size():
		var packed := load(str(paths[i])) as PackedScene
		var chunk := packed.instantiate() as Node2D if packed else null
		if chunk == null:
			push_error("Chunk %s failed to load" % paths[i])
			continue
		chunk.position = Vector2(i % chunks_x, i / chunks_x) * origin
		world_map.add_child(chunk)
		if i % CHUNKS_PER_FRAME == CHUNKS_PER_FRAME - 1:
			await get_tree().process_frame


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

	_map_layers.clear()
	for chunk_node in world_map.get_children():
		for child in chunk_node.get_children():
			if child is TileMapLayer:
				_register_layer(child)
	if sky_fill:
		_map_layers["sky"] = sky_fill
	_map_layers["artifacts"] = artifacts_layer
	_map_layers["machines"] = machines_layer
	_map_layers["actors"] = actors_layer
	return true
