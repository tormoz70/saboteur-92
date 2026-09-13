@tool
class_name LevelValidator
extends RefCounted

const ENTITIES_PATH := "res://assets/world/s2_entities.json"
const COLLISION_TILES_PATH := "res://assets/world/s2_collision_tiles.json"


func validate(level: Node) -> PackedStringArray:
	var errors: PackedStringArray = []
	if level == null:
		errors.append("No level node")
		return errors
	if level.get_node_or_null("CollisionLayer") == null:
		errors.append("Missing CollisionLayer")
	for name in ["Sky", "Earth", "Structure", "Wallpaper", "Mosaic", "Interior", "Foreground"]:
		if level.get_node_or_null(name) == null:
			errors.append("Missing visual layer %s" % name)
	if not FileAccess.file_exists(ENTITIES_PATH):
		errors.append("Missing spawn file s2_entities.json")
	else:
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(ENTITIES_PATH))
		if typeof(parsed) != TYPE_DICTIONARY or not parsed.has("spawn"):
			errors.append("Missing spawn point")
	var world := level.get_node_or_null("World")
	if world:
		if world.get_node_or_null("Lifts") == null:
			errors.append("Lifts missing — load the level in game once or keep s2_collision.json")
	if level.get_node_or_null("Entities/SpawnPoint") == null:
		errors.append("Missing spawn point")
	if FileAccess.file_exists(COLLISION_TILES_PATH):
		var tiles: Variant = JSON.parse_string(
			FileAccess.get_file_as_string(COLLISION_TILES_PATH)
		)
		if typeof(tiles) == TYPE_DICTIONARY:
			var runs: Array = tiles.get("rle", [])
			var ids := TileMapUtils.rle_decode(runs)
			var used := 0
			for i in ids.size():
				if ids[i] != TileMapUtils.TILE_EMPTY:
					used += 1
			if ids.size() > 0:
				var coverage := float(used) / float(ids.size())
				if coverage < 0.05:
					errors.append("Collision coverage too low: %.3f" % coverage)
			var climb := TileMapUtils.rle_decode(tiles.get("ladder_rle", []))
			var grid: Array = tiles.get("grid", [0, 0])
			if grid.size() >= 2:
				var orphans := _orphan_ladder_count(ids, climb, int(grid[0]), int(grid[1]))
				if orphans > 32:
					errors.append("Too many orphan ladder cells: %d" % orphans)
	return errors


func _orphan_ladder_count(
	ids: PackedInt32Array, climb: PackedInt32Array, cw: int, ch: int
) -> int:
	if cw <= 0 or ch <= 0:
		return 0
	var orphans := 0
	var n := mini(ids.size(), cw * ch)
	for i in n:
		var is_climb := false
		if i < climb.size() and climb[i] != 0:
			is_climb = true
		elif ids[i] == TileMapUtils.TILE_LADDER:
			is_climb = true
		if not is_climb:
			continue
		var x := i % cw
		var y := int(i / cw)
		var neighbor := false
		var dirs: Array[Vector2i] = [
			Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)
		]
		for d in dirs:
			var nx: int = x + d.x
			var ny: int = y + d.y
			if nx < 0 or ny < 0 or nx >= cw or ny >= ch:
				continue
			var ni: int = ny * cw + nx
			if ni >= n:
				continue
			if ids[ni] == TileMapUtils.TILE_SOLID or ids[ni] == TileMapUtils.TILE_LADDER:
				neighbor = true
				break
			if ni < climb.size() and climb[ni] != 0:
				neighbor = true
				break
		if not neighbor:
			orphans += 1
	return orphans
