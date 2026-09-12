@tool
class_name CollisionBrush
extends RefCounted

enum BrushType { SOLID, LADDER, ONEWAY, ERASE }

const TILE := {
	BrushType.SOLID: Vector2i(1, 0),
	BrushType.LADDER: Vector2i(2, 0),
	BrushType.ONEWAY: Vector2i(3, 0),
}

var current_brush: BrushType = BrushType.SOLID
var brush_size: int = 1
var painting := false


func collision_layer_from(root: Node) -> TileMapLayer:
	if root == null:
		return null
	return root.find_child("CollisionLayer", true, false) as TileMapLayer


func handle_canvas_input(event: InputEvent, editor: EditorInterface) -> bool:
	var layer := _edited_collision_layer(editor)
	if layer == null:
		return false
	var button := event as InputEventMouseButton
	if button and button.button_index == MOUSE_BUTTON_LEFT:
		if button.pressed:
			painting = true
			_paint_at(layer, button.position)
			return true
		painting = false
		return true
	var motion := event as InputEventMouseMotion
	if motion and painting:
		_paint_at(layer, motion.position)
		return true
	return false


func paint_cell(tilemap: TileMapLayer, cell: Vector2i) -> void:
	if tilemap == null:
		return
	for y in brush_size:
		for x in brush_size:
			var target := cell + Vector2i(x, y)
			if current_brush == BrushType.ERASE:
				tilemap.erase_cell(target)
			else:
				tilemap.set_cell(target, 0, TILE[current_brush])


func stamp_default_if_empty(collision: TileMapLayer, cell: Vector2i, kind: String) -> void:
	if collision == null:
		return
	if collision.get_cell_source_id(cell) != -1:
		return
	match kind:
		"solid", "floor", "ceiling":
			collision.set_cell(cell, 0, TILE[BrushType.SOLID])
		"climb":
			collision.set_cell(cell, 0, TILE[BrushType.LADDER])


func _edited_collision_layer(editor: EditorInterface) -> TileMapLayer:
	var scene := editor.get_edited_scene_root()
	if scene == null:
		return null
	var selected := editor.get_selection().get_selected_nodes()
	for node in selected:
		if node is TileMapLayer and node.name == "CollisionLayer":
			return node
		if str(node.name) == "CollisionLayer":
			return node as TileMapLayer
	return collision_layer_from(scene)


func _paint_at(layer: TileMapLayer, _canvas_pos: Vector2) -> void:
	paint_cell(layer, layer.local_to_map(layer.get_local_mouse_position()))
