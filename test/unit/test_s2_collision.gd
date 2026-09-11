extends GutTest
## Counts come from s2_collision.json, not from literals in this file.


func after_each() -> void:
	if Input.is_action_pressed("move_left"):
		Input.action_release("move_left")
	if Input.is_action_pressed("move_down"):
		Input.action_release("move_down")
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
	# Wallpaper (blue brick) is not a floor. Tunnel lining used to be grown
	# by thicken/fill; collision is object bounds now.
	var wallpaper: Array[Vector2i] = [
		Vector2i(2692, 3716),
		Vector2i(1028, 2852),
		Vector2i(940, 3572),
		Vector2i(2692, 3684),
		Vector2i(1028, 2824),
		Vector2i(940, 3540),
	]
	for p in wallpaper:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"cave wallpaper at %s must stay walkable" % p
		)


func test_cave_hall_floor_is_earth_not_wallpaper() -> void:
	var data := _collision_data()
	# Mosaic 7,15: yellow crates and a white ladder in a blue-brick hall.
	# Flooded-gap finding used to climb through the speckled earth and paint
	# the last wallpaper row as a floor, so Nina floated and her head hit
	# the hanging ceiling on the left. Stand on the earth; the paper lip
	# and the first earth cell under the thin tunnel stay empty.
	assert_false(
		_point_in_any_rect(Vector2i(1892, 2996), data["solids"]),
		"last wallpaper cell in the crate hall must not be the floor"
	)
	assert_true(
		_point_in_any_rect(Vector2i(1892, 3004), data["solids"]),
		"speckled earth under the crate hall should be solid"
	)
	assert_false(
		_point_in_any_rect(Vector2i(1804, 2964), data["solids"]),
		"standing volume under the hanging ceiling must stay walkable"
	)


func test_flooded_cave_gaps_are_walkable() -> void:
	var data := _collision_data()
	# Blue-brick wallpaper in a flooded corridor is not collision.
	var interiors: Array[Vector2i] = [
		Vector2i(5980, 2028),
		Vector2i(6196, 2028),
	]
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


func test_item_chrome_crates_are_walkable() -> void:
	var data := _collision_data()
	# Magenta ? supply boxes (mission code markers 02/06/11).
	var air: Array[Vector2i] = [
		Vector2i(808, 1536),
		Vector2i(1920, 392),
		Vector2i(4312, 1104),
	]
	for p in air:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"magenta item crate at %s must stay walkable" % p
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
	# Pure black is not filled as rock (no fill_cave_earth). Wallpaper stays air.
	assert_false(
		_point_in_any_rect(Vector2i(7236, 1948), data["solids"]),
		"blue brick hall interior must stay walkable"
	)


func test_dungeon_cracked_earth_is_the_floor() -> void:
	var data := _collision_data()
	# Mosaic 18,10: blue crack lines on black under the wallpaper. That cell
	# used to be punched so Nina stood a cell down in the dirt.
	assert_true(
		_point_in_any_rect(Vector2i(4788, 1996), data["solids"]),
		"cracked dungeon dirt should be the walkable floor"
	)
	assert_false(
		_point_in_any_rect(Vector2i(4788, 1988), data["solids"]),
		"blue brick above the cracks stays wallpaper"
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


func test_document_balcony_is_open() -> void:
	var data := _collision_data()
	# Document-room hatch (mosaic 8,3): dithered night sky beside the red lip
	# used to read as cave earth and block the balcony drop.
	# Night sky paper beside the hatch, not speckle that is earth.
	var air: Array[Vector2i] = [
		Vector2i(2248, 768),
		Vector2i(2120, 640),
	]
	for p in air:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"night sky beside the document hatch at %s must stay walkable" % p
		)
	assert_true(
		_point_in_any_rect(Vector2i(2248, 736), data["solids"]),
		"outdoor girder lip below the hatch should stay walkable"
	)


func test_code02_balcony_is_open() -> void:
	var data := _collision_data()
	# Marker 02 room (mosaic 3,8). Black + blue dots is earth, not night sky.
	# Pure blue paper is the drop; speckle beside the crate is ground.
	var earth: Array[Vector2i] = [
		Vector2i(760, 1536),
		Vector2i(736, 1520),
		Vector2i(1276, 1536),
	]
	for p in earth:
		assert_true(
			_point_in_any_rect(p, data["solids"]),
			"speckle earth at %s must be solid" % p
		)
	assert_false(
		_point_in_any_rect(Vector2i(700, 1536), data["solids"]),
		"pure blue sky west of crate 02 must stay a drop"
	)
	assert_true(
		_point_in_any_rect(Vector2i(800, 1560), data["solids"]),
		"red floor of the 02 room should stay solid"
	)


func test_code02_hatch_has_no_lip_wall() -> void:
	var data := _collision_data()
	# Hatch at 948: a 1-cell lid next to a 24px thickened floor made an 8px
	# cliff. Floor-snap caught it as a wall before the rungs.
	var air: Array[Vector2i] = [
		Vector2i(1000, 1544),
		Vector2i(976, 1544),
		Vector2i(960, 1544),
	]
	for p in air:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"approach to the 02 hatch at %s must stay walkable" % p
		)
	assert_true(
		_point_in_any_rect(Vector2i(960, 1560), data["solids"]),
		"hatch lid should be walkable"
	)
	assert_false(
		_point_in_any_rect(Vector2i(960, 1568), data["solids"]),
		"one-cell floor: shaft row below the lid must stay open"
	)
	assert_false(
		_point_in_any_rect(Vector2i(960, 1592), data["solids"]),
		"shaft under the hatch must stay open to climb down"
	)


func test_outdoor_lattice_scaffold_is_open() -> void:
	var data := _collision_data()
	# White X-lattice A-frames used to be painted as girder decks, so the
	# posts and hanging braces were 8px invisible walls in front of the ladder.
	var air: Array[Vector2i] = [
		Vector2i(3472, 200),
		Vector2i(6048, 576),
		Vector2i(6028, 688),
		Vector2i(6036, 688),
	]
	for p in air:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"outdoor lattice / A-frame at %s must stay walkable" % p
		)
	assert_true(
		_point_in_any_rect(Vector2i(2248, 736), data["solids"]),
		"document balcony girder lip should stay walkable"
	)


func test_office_crates_are_walkable() -> void:
	var data := _collision_data()
	# Yellow crate stacks in the spawn office (marker 03): furniture, not walls.
	var air: Array[Vector2i] = [
		Vector2i(2568, 800),
		Vector2i(2600, 824),
		Vector2i(2136, 816),
	]
	for p in air:
		assert_false(
			_point_in_any_rect(p, data["solids"]),
			"office crate at %s must stay walkable" % p
		)


func test_code02_walk_left_among_desks() -> void:
	# Live physics: standing east of the 02 hatch, walking left must pass the
	# desks and the hatch. JSON is empty there, but floor-snap used to catch
	# an 8px lid as a wall before the rungs.
	GameManager.reset_run_state()
	GameManager.state = GameManager.GameState.PLAYING
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	var player: Player = level.get_node("Player")
	# Origin is mosaic top-left. Floor at 1560; spawn uses y = floor - 56.
	player.global_position = Vector2(1040, 1560 - 56) * 2.0
	player.velocity = Vector2.ZERO
	await wait_physics_frames(8)
	assert_true(player.is_on_floor(), "should stand on the 02 office floor")
	var start_x := player.global_position.x
	Input.action_press("move_left")
	Input.action_press("move_down")
	for _i in 180:
		await wait_physics_frames(1)
		if player.global_position.x <= 900.0 * 2.0:
			break
	Input.action_release("move_left")
	Input.action_release("move_down")
	assert_false(player.on_ladder, "left+down must not drop into the 02 hatch")
	assert_lt(player.global_position.x, start_x - 40.0, "should have walked left")
	assert_lt(player.global_position.x, start_x - 40.0, "should have walked left")
	assert_lt(
		player.global_position.x,
		948.0 * 2.0,
		"should pass the 02 hatch toward the west opening"
	)
	assert_gt(player.global_position.y, (1560.0 - 80.0) * 2.0, "should stay on this floor")


func test_code02_walk_left_from_east_desks() -> void:
	# Same office, starting at the right-hand desks (the screenshot pose).
	GameManager.reset_run_state()
	GameManager.state = GameManager.GameState.PLAYING
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	var player: Player = level.get_node("Player")
	player.global_position = Vector2(1180, 1560 - 56) * 2.0
	player.velocity = Vector2.ZERO
	await wait_physics_frames(8)
	assert_true(player.is_on_floor())
	Input.action_press("move_left")
	for _i in 220:
		await wait_physics_frames(1)
		if player.global_position.x <= 820.0 * 2.0:
			break
	Input.action_release("move_left")
	assert_lt(
		player.global_position.x,
		900.0 * 2.0,
		"east desks must not hide a wall before the 02 crate"
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
	assert_null(
		level.get_node_or_null("Letterbox"),
		"side letterbox bars hide playable width the D-pad should sit in"
	)
