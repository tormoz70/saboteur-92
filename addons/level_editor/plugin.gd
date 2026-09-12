@tool
extends EditorPlugin

## Bottom-panel world tools. Never an autoload — editor-only, like mcp_bridge.

const PANEL_SCRIPT := preload("res://addons/level_editor/editor_panel.gd")
const BRUSH_SCRIPT := preload("res://addons/level_editor/collision_brush.gd")

var _panel: Control
var _brush: RefCounted


func _enter_tree() -> void:
	_brush = BRUSH_SCRIPT.new()
	_panel = PANEL_SCRIPT.new()
	_panel.brush = _brush
	_panel.plugin = self
	add_control_to_bottom_panel(_panel, "Level Editor")


func _exit_tree() -> void:
	if _panel:
		remove_control_from_bottom_panel(_panel)
		_panel.queue_free()
		_panel = null
	_brush = null


func _handles(object: Object) -> bool:
	return object is TileMapLayer


func _forward_canvas_gui_input(event: InputEvent) -> bool:
	if _brush == null:
		return false
	return _brush.handle_canvas_input(event, get_editor_interface())
