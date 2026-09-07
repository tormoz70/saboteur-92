extends SceneTree
## Check every TileMapLayer cell against s2_world_tiles.json.

const TILES_PATH := "res://assets/world/s2_world_tiles.json"

var _frames := 0


func _initialize() -> void:
	change_scene_to_file("res://scenes/main.tscn")


func _process(_dt: float) -> bool:
	_frames += 1
	if _frames < 16:
		return false
	_verify()
	quit()
	return false


func _verify() -> void:
	var main := root.get_child(root.get_child_count() - 1)
	var level: Node2D = main.get_node_or_null("Level01") as Node2D
	if level == null:
		push_error("verify_tiles: Level01 missing")
		return
	var visual: TileMapLayer = level.get_node("Visual")
	var fg: TileMapLayer = level.get_node("Foreground")
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(TILES_PATH))
	var tiles: Dictionary = parsed
	var cw := int(tiles["grid"][0])
	var wmiss := _count_mismatches(visual, tiles["world"], cw, false)
	var fmiss := _count_mismatches(fg, tiles["fg"], cw, true)
	print("verify_tiles: world_mismatches=%d fg_mismatches=%d" % [wmiss, fmiss])


func _count_mismatches(layer: TileMapLayer, spec: Dictionary, cw: int, skip_empty: bool) -> int:
	var atlas_cols := int(spec["atlas_tiles"][0])
	var empty_id := int(spec["empty"]) if spec.get("empty", null) != null else -1
	var rle: Array = spec["rle"]
	var mismatches := 0
	var checked := 0
	var used := 0
	var cell_i := 0
	var i := 0
	while i < rle.size():
		var tid := int(rle[i])
		var count := int(rle[i + 1])
		i += 2
		for _n in count:
			var coords := Vector2i(cell_i % cw, cell_i / cw)
			var got := layer.get_cell_source_id(coords)
			var atlas := layer.get_cell_atlas_coords(coords)
			if skip_empty and tid == empty_id:
				if got != -1:
					mismatches += 1
			else:
				var exp := Vector2i(tid % atlas_cols, tid / atlas_cols)
				if got != 0 or atlas != exp:
					mismatches += 1
					if mismatches <= 8:
						print(
							" mismatch %s cell %s got source=%d atlas=%s expected=%s tid=%d"
							% [layer.name, coords, got, atlas, exp, tid]
						)
				else:
					used += 1
			checked += 1
			cell_i += 1
	print("  %s checked=%d used=%d mismatches=%d" % [layer.name, checked, used, mismatches])
	return mismatches
