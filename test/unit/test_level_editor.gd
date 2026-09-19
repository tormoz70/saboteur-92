extends GutTest


func test_validator_flags_empty_node() -> void:
	var validator = load("res://addons/level_editor/level_validator.gd").new()
	var node := Node2D.new()
	add_child_autofree(node)
	var errors: PackedStringArray = validator.validate(node)
	assert_gt(errors.size(), 0, "empty node is invalid")


func test_validator_accepts_level_template() -> void:
	var packed: PackedScene = load("res://scenes/levels/level_template.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	var validator = load("res://addons/level_editor/level_validator.gd").new()
	var errors: PackedStringArray = validator.validate(level)
	assert_eq(errors.size(), 0, "; ".join(errors))
