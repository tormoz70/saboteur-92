@tool
class_name LevelEditorSync
extends RefCounted

## Stamp a default collision cell when a visual tile is painted on empty air.
## Never overwrites an already painted collision cell.

const DEFAULT_KIND := {
	"Earth": "solid",
	"Structure": "solid",
}


func handle_visual_input(event: InputEvent, brush: CollisionBrush) -> void:
	if brush == null:
		return
	var button := event as InputEventMouseButton
	var motion := event as InputEventMouseMotion
	var paint := false
	if button and button.button_index == MOUSE_BUTTON_LEFT and button.pressed:
		paint = true
	elif motion and Input.is_mouse_button_pressed(MOUSE_BUTTON_LEFT):
		paint = true
	if not paint:
		return
	var visual := _edited_visual_layer()
	if visual == null:
		return
	var kind := str(DEFAULT_KIND.get(str(visual.name), ""))
	if kind == "":
		return
	var scene := EditorInterface.get_edited_scene_root()
	var collision := brush.collision_layer_from(scene)
	var cell := visual.local_to_map(visual.get_local_mouse_position())
	brush.stamp_default_if_empty(collision, cell, kind)


func _edited_visual_layer() -> TileMapLayer:
	var selected := EditorInterface.get_selection().get_selected_nodes()
	for node in selected:
		if node is TileMapLayer and str(node.name) != "CollisionLayer":
			return node as TileMapLayer
	return null
