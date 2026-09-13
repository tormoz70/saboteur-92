@tool
extends Control

var plugin
var brush: CollisionBrush

var _status: Label
var _exporter: LevelJsonExport
var _validator: LevelValidator


func _ready() -> void:
	name = "LevelEditor"
	custom_minimum_size = Vector2(180, 140)
	set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_exporter = LevelJsonExport.new()
	_validator = LevelValidator.new()
	var root := VBoxContainer.new()
	root.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	root.offset_left = 8
	root.offset_top = 8
	root.offset_right = -8
	root.offset_bottom = -8
	add_child(root)
	var title := Label.new()
	title.text = "Level Editor"
	root.add_child(title)
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
	_status.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_status.text = "Open level_01.tscn or screen_spawn.tscn, then Load JSON."
	root.add_child(_status)


func _add_button(parent: Node, text: String, cb: Callable) -> void:
	var btn := Button.new()
	btn.text = text
	btn.pressed.connect(cb)
	parent.add_child(btn)


func _set_brush(kind: int) -> void:
	if brush:
		brush.current_brush = kind
	_status.text = "Brush %d — select CollisionLayer, paint in 2D view" % kind


func _on_brush_size(value: float) -> void:
	if brush:
		brush.brush_size = int(value)


func _level() -> Node:
	return EditorInterface.get_edited_scene_root()


func _on_load() -> void:
	var level := _level()
	if level == null:
		_say("Open level_01.tscn or screen_spawn.tscn first")
		return
	_say("Loading world JSON…")
	var result: Dictionary = _exporter.import_into_level(level)
	if not bool(result.get("ok", false)):
		_say(str(result.get("error", "Load failed")))
		push_error("Level Editor Load JSON: %s" % result.get("error", ""))
		return
	var sky := level.get_node_or_null("Sky")
	if sky:
		EditorInterface.edit_node(sky)
	if EditorInterface.has_method("set_main_screen_editor"):
		EditorInterface.set_main_screen_editor("2D")
	_say("Loaded %d tiles. Do not save level_01.tscn — use Save JSON." % int(result.get("cells", 0)))
	print("Level Editor: loaded %s cells into %s" % [result.get("cells", 0), level.name])


func _on_save() -> void:
	var level := _level()
	if level == null:
		_say("Open a level scene first")
		return
	_exporter.export_from_level(level)
	_say("Saved s2_world_tiles.json + s2_collision_tiles.json")


func _on_validate() -> void:
	var errors: PackedStringArray = _validator.validate(_level())
	if errors.is_empty():
		_say("Level OK")
	else:
		_say("; ".join(errors))


func _say(text: String) -> void:
	if _status:
		_status.text = text
	print("Level Editor: ", text)
