@tool
extends EditorPlugin

## Editor-only world tools. Never an autoload.

const PANEL_SCRIPT := preload("res://addons/level_editor/editor_panel.gd")
const BRUSH_SCRIPT := preload("res://addons/level_editor/collision_brush.gd")
const SYNC_SCRIPT := preload("res://addons/level_editor/level_editor_sync.gd")

var _dock
var _bottom
var _brush: CollisionBrush
var _sync: LevelEditorSync


func _enter_tree() -> void:
	_brush = BRUSH_SCRIPT.new()
	_sync = SYNC_SCRIPT.new()
	_dock = PANEL_SCRIPT.new()
	_dock.brush = _brush
	_dock.plugin = self
	add_control_to_dock(DOCK_SLOT_LEFT_BL, _dock)
	_bottom = PANEL_SCRIPT.new()
	_bottom.brush = _brush
	_bottom.plugin = self
	add_control_to_bottom_panel(_bottom, "Level Editor")
	print("Level Editor ready: FileSystem tabs (left) or bottom bar next to GUT")


func _exit_tree() -> void:
	if _bottom:
		remove_control_from_bottom_panel(_bottom)
		_bottom.queue_free()
		_bottom = null
	if _dock:
		remove_control_from_docks(_dock)
		_dock.queue_free()
		_dock = null
	_brush = null
	_sync = null


func _handles(object: Object) -> bool:
	return object is TileMapLayer


func _forward_canvas_gui_input(event: InputEvent) -> bool:
	if _brush == null:
		return false
	var consumed := _brush.handle_canvas_input(event)
	if not consumed and _sync:
		_sync.handle_visual_input(event, _brush)
	return consumed
