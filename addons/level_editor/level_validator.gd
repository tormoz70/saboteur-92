@tool
class_name LevelValidator
extends RefCounted

## Validates a level scene (or a single world chunk) in the native model:
## tile data lives in the scene's TileMapLayer nodes, semantics lives in the
## CollisionLayer via the collision TileSet custom data.


func validate(level: Node) -> PackedStringArray:
	var errors: PackedStringArray = []
	if level == null:
		errors.append("No level node")
		return errors

	var collision := _find_layer(level, "CollisionLayer")
	if collision == null:
		errors.append("Missing CollisionLayer")
	elif collision.tile_set == null:
		errors.append("CollisionLayer has no TileSet")

	var any_visual := false
	for name in ["Earth", "Structure", "Wallpaper", "Mosaic", "Interior", "Foreground"]:
		var layer := _find_layer(level, name)
		if layer == null:
			continue
		any_visual = true
		if layer.tile_set == null:
			errors.append("Visual layer %s has no TileSet" % name)
	if not any_visual:
		errors.append("No visual tile layers found")

	# A full level must be able to spawn the player. Chunks have no SpawnPoint,
	# so this only applies to scenes that carry an Entities node.
	if level.get_node_or_null("Entities") != null:
		if level.get_node_or_null("Entities/SpawnPoint") == null:
			errors.append("Missing spawn point")

	if collision:
		var ladder_cells := 0
		for cell in collision.get_used_cells():
			if TileMapUtils.get_collision_type(collision, cell) == "ladder":
				ladder_cells += 1
		var orphan := _orphan_ladder_count(collision)
		if orphan > 32:
			errors.append("Too many orphan ladder cells: %d" % orphan)
	return errors


func _find_layer(root: Node, node_name: String) -> TileMapLayer:
	if root == null:
		return null
	return root.find_child(node_name, true, false) as TileMapLayer


func _orphan_ladder_count(collision: TileMapLayer) -> int:
	var orphans := 0
	var dirs: Array[Vector2i] = [
		Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)
	]
	for cell in collision.get_used_cells():
		if TileMapUtils.get_collision_type(collision, cell) != "ladder":
			continue
		var neighbor := false
		for d in dirs:
			var n := cell + d
			if collision.get_cell_source_id(n) == -1:
				continue
			var kind := TileMapUtils.get_collision_type(collision, n)
			if kind == "solid" or kind == "ladder":
				neighbor = true
				break
		if not neighbor:
			orphans += 1
	return orphans
