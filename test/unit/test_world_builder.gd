extends GutTest
## WorldBuilder: JSON chunks rebuild the authored .tscn chunks and spawn
## entities the way LevelBase does.


func _cells(layer: TileMapLayer) -> Dictionary:
	var d := {}
	for c in layer.get_used_cells():
		d[c] = [layer.get_cell_source_id(c), layer.get_cell_atlas_coords(c),
			layer.get_cell_alternative_tile(c)]
	return d


func _json(path: String) -> Dictionary:
	return JSON.parse_string(FileAccess.get_file_as_string(path))


func test_rebuilds_every_chunk_cell_for_cell() -> void:
	var builder := WorldBuilder.new()
	var mismatched: Array = []
	var cells := 0
	for cy in 8:
		for cx in 8:
			var id := "chunk_%02d_%02d" % [cx, cy]
			var src: Node = load("res://scenes/world/chunks/%s.tscn" % id).instantiate()
			var built := builder.build(_json("res://assets/world/chunks_json/%s.json" % id))
			var src_names: Array = []
			var built_names: Array = []
			for layer in src.get_children():
				if not layer is TileMapLayer:
					continue
				src_names.append(layer.name)
				var other := built.get_node_or_null(NodePath(layer.name)) as TileMapLayer
				var expected := _cells(layer)
				cells += expected.size()
				if other == null or _cells(other) != expected \
						or other.z_index != layer.z_index or other.visible != layer.visible \
						or other.tile_set.resource_path != layer.tile_set.resource_path:
					mismatched.append("%s/%s" % [id, layer.name])
			for layer in built.get_children():
				if layer is TileMapLayer and layer.name in src_names:
					built_names.append(layer.name)
			if src_names != built_names:
				mismatched.append("%s node order %s" % [id, built_names])
			src.free()
			built.free()
	assert_gt(cells, 600000)
	assert_eq(mismatched, [])


func test_entities_get_game_properties() -> void:
	var builder := WorldBuilder.new()
	builder.world_scale = 2.0
	var root := builder.build(_json("res://assets/world/chunks_json/chunk_02_01.json"))
	var key := root.get_node("Entities/key")
	assert_eq(key.scene_file_path, "res://scenes/items/pickup.tscn")
	assert_eq(key.item_type, "key")
	assert_eq(key.position, Vector2(54, 13) * 8.0)
	var guard := root.get_node("Entities/ground")
	assert_eq(guard.patrol_distance, 160.0, "native px patrol times world_scale")
	var spawn := root.get_node("Entities/spawn")
	assert_true(spawn is Marker2D)
	assert_eq(spawn.get_meta("entity_params").origin, "top_left")
	root.free()


func test_invuln_bonus_is_a_pickup() -> void:
	var root := WorldBuilder.new().build(_json("res://assets/world/chunks_json/chunk_00_03.json"))
	var bonus := root.get_node("Entities/bonus")
	assert_eq(bonus.scene_file_path, "res://scenes/items/pickup.tscn")
	assert_eq(bonus.item_type, "invuln")
	root.free()


func test_unknown_entity_type_becomes_marker_with_params() -> void:
	var chunk := {
		"chunk_id": "t", "grid_size": [4, 4], "cell_size": 8, "layers": {},
		"entities": [{"type": "teleporter", "id": "tp", "position": [1, 2], "params": {"to": "b"}}],
	}
	var root := WorldBuilder.new().build(chunk, _json("res://assets/tilesets/tile_id_map.json"))
	var tp := root.get_node("Entities/tp")
	assert_true(tp is Marker2D)
	assert_eq(tp.get_meta("entity_type"), "teleporter")
	assert_eq(tp.get_meta("entity_params"), {"to": "b"})
	root.free()


func test_malformed_layer_is_left_empty() -> void:
	var chunk := {
		"chunk_id": "t", "grid_size": [4, 2], "cell_size": 8,
		"layers": {"collision": {"encoding": "rle", "data": [2, 3]}},
	}
	var root := WorldBuilder.new().build(chunk, _json("res://assets/tilesets/tile_id_map.json"))
	var layer := root.get_node("CollisionLayer") as TileMapLayer
	assert_eq(layer.get_used_cells().size(), 0)
	assert_push_error("rle covers 3 of 8 cells")
	root.free()
