extends GutTest


func test_validator_flags_empty_node() -> void:
	var validator = load("res://addons/level_editor/level_validator.gd").new()
	var node := Node2D.new()
	add_child_autofree(node)
	var errors: PackedStringArray = validator.validate(node)
	assert_gt(errors.size(), 0, "empty node is invalid")


func test_export_helper_rle_matches() -> void:
	var exporter = load("res://addons/level_editor/export_json.gd").new()
	var a: Array = [1, 3, 0, 2]
	assert_true(exporter.rle_matches(a, a.duplicate()))
	assert_false(exporter.rle_matches(a, [1, 2]))
