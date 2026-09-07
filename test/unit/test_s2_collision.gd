extends GutTest
## Counts come from s2_collision.json, not from literals in this file.


func after_each() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func _collision_data() -> Dictionary:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	return parsed


func test_collision_json_has_solids_ladders_and_lifts() -> void:
	var data := _collision_data()
	assert_gt(data.get("solids", []).size(), 0, "solids array")
	assert_gt(data.get("ladders", []).size(), 0, "ladders array")
	assert_gt(data.get("lifts", []).size(), 0, "lifts array")
	for rect in data["solids"]:
		assert_eq(rect.size(), 4, "solid is [x, y, w, h]")
	for rect in data["ladders"]:
		assert_eq(rect.size(), 4, "ladder is [x, y, w, h]")
	for spec in data["lifts"]:
		assert_true(spec.has("x") and spec.has("y") and spec.has("w") and spec.has("h"))
		assert_true(spec.has("top") and spec.has("bottom"))


func test_outdoor_sky_rail_ladders_are_climbable() -> void:
	var data := _collision_data()
	# White-on-blue shafts that continue the interior green pair into the sky
	# on the green rooftop screen (mosaic 9,8) the player circled.
	var samples: Array[Vector2i] = [
		Vector2i(2352, 1664),
		Vector2i(2440, 1664),
		Vector2i(1976, 264),
		Vector2i(3000, 408),
	]
	for p in samples:
		assert_true(
			_point_in_any_rect(p, data["ladders"]),
			"outdoor sky rail at %s should be a ladder" % p
		)


func _point_in_any_rect(p: Vector2i, rects: Array) -> bool:
	for rect in rects:
		if (
			p.x >= int(rect[0])
			and p.x < int(rect[0]) + int(rect[2])
			and p.y >= int(rect[1])
			and p.y < int(rect[1]) + int(rect[3])
		):
			return true
	return false


func test_level_builds_one_shape_per_json_entry() -> void:
	var data := _collision_data()
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	var solids: Node = level.get_node("World/Solids")
	var ladders: Node = level.get_node("World/Ladders")
	var lifts: Node = level.get_node("World/Lifts")
	assert_eq(solids.get_child_count(), data["solids"].size())
	assert_eq(ladders.get_child_count(), data["ladders"].size())
	assert_eq(lifts.get_child_count(), data["lifts"].size())
