extends GutTest
## Counts come from s2_collision.json, not from literals in this file.


func after_each() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func _collision_data() -> Dictionary:
	var parsed: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	assert_typeof(parsed, TYPE_DICTIONARY)
	return parsed


func test_collision_json_has_solids_ladders_and_lifts() -> void:
	var data := _collision_data()
	assert_gt(data.get("solids", []).size(), 0, "solids array")
	assert_gt(data.get("ladders", []).size(), 0, "ladders array")
	assert_gt(data.get("lifts", []).size(), 0, "lifts array")
	for rect in data["solids"]:
		assert_eq(rect.size(), 4, "solid is [x, y, w, h]")
	for rect in data["ladders"]:
		assert_eq(rect.size(), 4, "ladder is [x, y, w, h]")
	for spec in data["lifts"]:
		assert_true(spec.has("x") and spec.has("y") and spec.has("w") and spec.has("h"))
		assert_true(spec.has("top") and spec.has("bottom"))


func test_outdoor_sky_rail_ladders_are_climbable() -> void:
	var data := _collision_data()
	# White-on-blue shafts that continue the interior green pair into the sky
	# on the green rooftop screen (mosaic 9,8) the player circled.
	var samples: Array[Vector2i] = [
		Vector2i(2352, 1664),
		Vector2i(2440, 1664),
		Vector2i(1976, 264),
		Vector2i(3000, 408),
	]
	for p in samples:
		assert_true(
			_point_in_any_rect(p, data["ladders"]),
			"outdoor sky rail at %s should be a ladder" % p
		)


func test_diamond_slabs_are_walkable_solids() -> void:
	var data := _collision_data()
	# White diamond room-dividers (green wallpaper above, blue brick below)
	# and the same character on outdoor girder decks.
	var samples: Array[Vector2i] = [
		Vector2i(2844, 3012),
		Vector2i(3380, 3012),
		Vector2i(1868, 2716),
		Vector2i(1108, 964),
	]
	for p in samples:
		assert_true(
			_point_in_any_rect(p, data["solids"]),
			"diamond slab at %s should be solid" % p
		)
	assert_false(
		_point_in_any_rect(Vector2i(2844, 3004), data["solids"]),
		"cell above the diamond slab must stay empty so the top is walkable"
	)
	assert_false(
		_point_in_any_rect(Vector2i(2844, 3020), data["solids"]),
		"blue brick under the slab is the room below, not extra floor thickness"
	)


func test_cave_tunnels_have_floor_and_ceiling() -> void:
	var data := _collision_data()
	# Thin blue-brick cave corridors: jagged lining is solid, wallpaper inside
	# stays empty. Samples are mosaic pixels (cell centres).
	var floors: Array[Vector2i] = [
		Vector2i(2692, 3716),
		Vector2i(1028, 2852),
		Vector2i(940, 3572),
	]
	var ceils: Array[Vector2i] = [
		Vector2i(2692, 3660),
		Vector2i(1028, 2796),
		Vector2i(940, 3508),
	]
	var interiors: Array[Vector2i] = [
		Vector2i(2692, 3684),
		Vector2i(1028, 2824),
		Vector2i(940, 3540),
	]
	for p in floors:
		assert_true(
			_point_in_any_rect(p, data["solids"]),
			"cave tunnel floor at %s should be solid" % p
		)
	for p in ceils:
		assert_true(
			_point_in_any_rect(p, data["solids"]),
			"cave tunnel ceiling at %s should be solid" % p
		)
	for p in interiors:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"cave tunnel interior at %s must stay walkable" % p
		)


func test_flooded_cave_gaps_are_walkable() -> void:
	var data := _collision_data()
	# Black corridor between two blue-brick masses: air (and water in the
	# lower half) with lining on the inner brick edges. Mosaic cell centres.
	var floors: Array[Vector2i] = [
		Vector2i(5980, 2076),
		Vector2i(6196, 2076),
	]
	var ceils: Array[Vector2i] = [
		Vector2i(5980, 1988),
		Vector2i(6196, 1988),
	]
	var interiors: Array[Vector2i] = [
		Vector2i(5980, 2028),
		Vector2i(6196, 2028),
	]
	for p in floors:
		assert_true(
			_point_in_any_rect(p, data["solids"]),
			"flooded tunnel floor at %s should be solid" % p
		)
	for p in ceils:
		assert_true(
			_point_in_any_rect(p, data["solids"]),
			"flooded tunnel ceiling at %s should be solid" % p
		)
	for p in interiors:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"flooded tunnel interior at %s must stay walkable" % p
		)


func test_red_pillars_are_passable() -> void:
	var data := _collision_data()
	# Thin red posts in the green interior room (mosaic 8,15): supports, not
	# walls. Mosaic cell centres of the left post, right post, and the red
	# brick floor they stand on.
	var posts: Array[Vector2i] = [
		Vector2i(2060, 2964),
		Vector2i(2260, 2916),
	]
	for p in posts:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"red pillar at %s must stay walkable" % p
		)
	assert_true(
		_point_in_any_rect(Vector2i(2164, 3004), data["solids"]),
		"red brick floor under the pillars should stay solid"
	)


func test_crates_and_blue_brick_are_not_solid() -> void:
	var data := _collision_data()
	# Mosaic 8,15: yellow crates and the blue-brick far wall around them.
	# Furniture and basement wallpaper are walk-behind, not walls.
	var air: Array[Vector2i] = [
		Vector2i(2052, 2948),
		Vector2i(2076, 2972),
		Vector2i(2100, 2980),
	]
	for p in air:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"crate/blue brick at %s must stay walkable" % p
		)


func test_blue_wallpaper_above_diamond_is_not_a_floor() -> void:
	var data := _collision_data()
	# Mosaic 7,14: cave paper sitting on the diamond slab used to be marked as
	# a tunnel floor and blocked walking left at chest height.
	assert_false(
		_point_in_any_rect(Vector2i(1764, 2708), data["solids"]),
		"blue wallpaper above the diamond must stay walkable"
	)
	assert_true(
		_point_in_any_rect(Vector2i(1868, 2716), data["solids"]),
		"diamond slab should stay solid"
	)


func test_cave_hall_black_is_ground() -> void:
	var data := _collision_data()
	# Mosaic 28,10: tall blue-brick cave hall. Black ceiling mass on the
	# right, black floor below — not a thin 8-cell tunnel, so lining used
	# to be missing and Nina walked through the rock.
	assert_true(
		_point_in_any_rect(Vector2i(7372, 1932), data["solids"]),
		"cave hall ceiling mass should be solid"
	)
	assert_true(
		_point_in_any_rect(Vector2i(7332, 2044), data["solids"]),
		"cave hall floor mass should be solid"
	)
	assert_false(
		_point_in_any_rect(Vector2i(7236, 1948), data["solids"]),
		"blue brick hall interior must stay walkable"
	)


func test_cave_hall_ladder_is_reachable_at_standing_height() -> void:
	var data := _collision_data()
	# Mosaic 28,10: the jagged right edge of the hall used to get a tunnel
	# floor / cave-ground slab at chest height, so Nina could see the white
	# ladder but could not walk to it.
	var air: Array[Vector2i] = [
		Vector2i(7244, 1964),
		Vector2i(7260, 1964),
		Vector2i(7284, 1956),
		# Leftover 8px hall-step stubs sat in the standing volume and blocked
		# the last walk to the white ladder (and the matching hall at mosaic 22,10).
		Vector2i(7236, 1980),
		Vector2i(7252, 1972),
		Vector2i(5612, 1980),
		Vector2i(5628, 1972),
	]
	for p in air:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"path to the hall ladder at %s must stay walkable" % p
		)


func _point_in_any_rect(p: Vector2i, rects: Array) -> bool:
	for rect in rects:
		if (
			p.x >= int(rect[0])
			and p.x < int(rect[0]) + int(rect[2])
			and p.y >= int(rect[1])
			and p.y < int(rect[1]) + int(rect[3])
		):
			return true
	return false


func test_level_builds_one_shape_per_json_entry() -> void:
	var data := _collision_data()
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	var solids: Node = level.get_node("World/Solids")
	var ladders: Node = level.get_node("World/Ladders")
	var lifts: Node = level.get_node("World/Lifts")
	assert_eq(solids.get_child_count(), data["solids"].size())
	assert_eq(ladders.get_child_count(), data["ladders"].size())
	assert_eq(lifts.get_child_count(), data["lifts"].size())
