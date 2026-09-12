@tool
extends Control

var plugin: EditorPlugin
var brush: RefCounted

var _status: Label
var _exporter = preload("res://addons/level_editor/export_json.gd").new()
var _validator = preload("res://addons/level_editor/level_validator.gd").new()


func _ready() -> void:
	custom_minimum_size = Vector2(0, 120)
	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(root)
	var row := HBoxContainer.new()
	root.add_child(row)
	_add_button(row, "Load JSON", _on_load)
	_add_button(row, "Save JSON", _on_save)
	_add_button(row, "Validate", _on_validate)
	var brush_row := HBoxContainer.new()
	root.add_child(brush_row)
	_add_button(brush_row, "Solid", func() -> void: _set_brush(0))
	_add_button(brush_row, "Ladder", func() -> void: _set_brush(1))
	_add_button(brush_row, "Oneway", func() -> void: _set_brush(2))
	_add_button(brush_row, "Erase", func() -> void: _set_brush(3))
	var size_spin := SpinBox.new()
	size_spin.min_value = 1
	size_spin.max_value = 8
	size_spin.value = 1
	size_spin.value_changed.connect(_on_brush_size)
	brush_row.add_child(size_spin)
	_status = Label.new()
	_status.text = "Collision brush: paint CollisionLayer in the 2D view."
	root.add_child(_status)


func _add_button(parent: Node, text: String, cb: Callable) -> void:
	var btn := Button.new()
	btn.text = text
	btn.pressed.connect(cb)
	parent.add_child(btn)


func _set_brush(kind: int) -> void:
	if brush:
		brush.current_brush = kind
	_status.text = "Brush %d" % kind


func _on_brush_size(value: float) -> void:
	if brush:
		brush.brush_size = int(value)


func _level() -> Node:
	if plugin == null:
		return null
	return plugin.get_editor_interface().get_edited_scene_root()


func _on_load() -> void:
	var level := _level()
	_exporter.import_into_level(level)
	_status.text = "Loaded world JSON into TileMapLayers"


func _on_save() -> void:
	var level := _level()
	_exporter.export_from_level(level)
	_status.text = "Saved s2_world_tiles.json + s2_collision_tiles.json"


func _on_validate() -> void:
	var errors := _validator.validate(_level())
	if errors.is_empty():
		_status.text = "Level OK"
	else:
		_status.text = "; ".join(errors)
