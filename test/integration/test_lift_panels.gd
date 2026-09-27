extends GutTest
## Level 01 lifts: call panels answer a punch, and an empty top station is an
## open shaft. Coordinates are native px from s2_entities.json / s2_collision.json.

const SCALE := 2.0
# Nina's origin is the sprite's top-left: body centre +48, feet +112 at scale 2.
const BODY_DX := 48.0
const FEET_DY := 112.0


func after_each() -> void:
	for action in ["punch", "move_left", "move_right"]:
		Input.action_release(action)
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func _spawn_level() -> Node2D:
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	while not level.world_loaded:
		await get_tree().process_frame
	return level


func _lift_at(level: Node2D, native_x: float) -> Lift:
	for lift in level.get_tree().get_nodes_in_group("lifts"):
		if absf(lift.global_position.x - native_x * SCALE) <= 4.0:
			return lift
	return null


func _place(player: Player, body_x: float, feet_y: float) -> void:
	player.global_position = Vector2(body_x - BODY_DX, feet_y - FEET_DY - 2.0)
	player.velocity = Vector2.ZERO


func test_every_panel_is_wired_to_its_lift() -> void:
	var level := await _spawn_level()
	var panels := level.get_node("LiftPanels").get_children()
	assert_eq(panels.size(), 6, "a call panel at both stations of all three lifts")
	for panel in panels:
		assert_not_null(panel.lift, "%s has a lift" % panel.name)


func test_punching_bottom_panel_sends_cabin_down() -> void:
	var level := await _spawn_level()
	var player: Player = level.player
	var lift := _lift_at(level, 5416.0)
	assert_not_null(lift)
	assert_true(lift.at_top(), "lift 3 starts at its top station")
	# Bottom panel of lift 3 at (6036, 3268), floor at 3288; punch from its left.
	_place(player, 6036.0 * SCALE - 60.0, 3288.0 * SCALE)
	player.apply_facing(1)
	await wait_physics_frames(10)
	assert_true(player.is_on_floor())
	assert_eq(lift.dir, 0)
	Input.action_press("punch")
	await wait_physics_frames(6)
	Input.action_release("punch")
	assert_eq(lift.dir, 1, "the punch calls the cabin down")


func test_empty_top_station_is_an_open_shaft() -> void:
	var level := await _spawn_level()
	var player: Player = level.player
	var lift := _lift_at(level, 2600.0)
	assert_not_null(lift)
	assert_true(lift.at_bottom(), "lift 1 waits at its bottom station")
	var top := lift.top_y
	_place(player, lift.center_x(), top)
	await wait_physics_frames(60)
	assert_gt(player.global_position.y + FEET_DY, top + 200.0, "Nina drops down the tube")
