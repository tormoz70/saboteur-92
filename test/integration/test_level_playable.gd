extends GutTest
## Level 01 (chunked Saboteur II map) playability gate.
##
## The map lives in 64 instanced chunk scenes under WorldMap; physics comes
## from the collision TileSet (no StaticBody2D "Solids" is built in code).
## These checks assert the chunks instance with tiles, ladders/lifts are built
## from the collision data, and the spawn point is not embedded in solid.


func after_each() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func _spawn_level() -> Node2D:
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	# _ready() streams chunks in over several frames, then builds ladders/lifts.
	while not level.world_loaded:
		await get_tree().process_frame
	return level


func _collision_type_at(level: Node2D, world_pos: Vector2) -> String:
	for source in level._collision_sources():
		var layer: TileMapLayer = source[0]
		var cell := layer.local_to_map(layer.to_local(world_pos))
		var data := layer.get_cell_tile_data(cell)
		if data:
			var ct := str(data.get_custom_data("collision_type"))
			if ct != "" and ct != "empty":
				return ct
	return "empty"


func test_chunks_instance_with_tiles() -> void:
	var level := await _spawn_level()
	var world_map := level.get_node("WorldMap")
	assert_eq(world_map.get_child_count(), 64, "64 chunk scenes instance")
	var collision_tiles := 0
	var visual_tiles := 0
	for chunk in world_map.get_children():
		for layer in chunk.get_children():
			if not layer is TileMapLayer:
				continue
			if layer.name == "CollisionLayer":
				collision_tiles += (layer as TileMapLayer).get_used_cells().size()
			else:
				visual_tiles += (layer as TileMapLayer).get_used_cells().size()
	assert_gt(visual_tiles, 0, "visual tiles across chunks")
	assert_gt(collision_tiles, 0, "collision tiles across chunks")


func test_ladders_and_lifts_built() -> void:
	var level := await _spawn_level()
	var ladders := level.get_node_or_null("World/Ladders")
	var lifts := level.get_node_or_null("World/Lifts")
	assert_not_null(ladders, "World/Ladders node")
	assert_not_null(lifts, "World/Lifts node")
	if ladders:
		assert_gt(ladders.get_child_count(), 0, "ladder areas built from collision tiles")
	if lifts:
		assert_gt(lifts.get_child_count(), 0, "lifts built from collision data")


func test_spawn_not_inside_solid() -> void:
	var level := await _spawn_level()
	var player := level.get_node("Player") as Node2D
	assert_not_null(player, "Player node")
	# Player origin is top-left; the body sits ~24px in and 35-56px down
	# (sprite-local), scaled by the level scale. Sample the body column.
	var scale: float = level._scale
	var body_top: Vector2 = player.global_position + Vector2(31, 40) * scale
	var body_feet: Vector2 = player.global_position + Vector2(31, 55) * scale
	assert_ne(_collision_type_at(level, body_top), "solid", "spawn body not in solid")
	assert_ne(_collision_type_at(level, body_feet), "solid", "spawn feet not in solid")
