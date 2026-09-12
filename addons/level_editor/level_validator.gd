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
	for name in ["Sky", "Earth", "Structure", "Wallpaper", "Interior", "Foreground"]:
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
	return errors
