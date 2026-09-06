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
