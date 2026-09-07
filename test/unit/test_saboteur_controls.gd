extends GutTest
## Saboteur II inlay table: UP/FIRE chords, no dedicated jump button.


func after_each() -> void:
	for action in ["move_up", "move_down", "jump", "punch", "move_left", "move_right"]:
		if Input.is_action_pressed(action):
			Input.action_release(action)


func test_still_up_is_stand_kick() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, true, false, false, false),
		SaboteurControls.GroundAction.STAND_KICK
	)


func test_moving_up_is_running_jump() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(true, true, false, false, false),
		SaboteurControls.GroundAction.RUNNING_JUMP
	)


func test_moving_up_on_ladder_is_still_running_jump() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(true, true, false, true, false),
		SaboteurControls.GroundAction.RUNNING_JUMP
	)


func test_still_up_on_ladder_defers_to_climb() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, true, false, true, false),
		SaboteurControls.GroundAction.NONE
	)


func test_up_on_usable_lift_defers_to_lift() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, true, false, false, true),
		SaboteurControls.GroundAction.NONE
	)


func test_up_on_dead_end_lift_is_stand_kick() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, true, false, false, false),
		SaboteurControls.GroundAction.STAND_KICK
	)


func test_moving_up_on_dead_end_lift_is_running_jump() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(true, true, false, false, false),
		SaboteurControls.GroundAction.RUNNING_JUMP
	)


func test_still_fire_is_punch() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, false, true, false, false),
		SaboteurControls.GroundAction.PUNCH
	)


func test_moving_fire_is_flying_kick() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(true, false, true, false, false),
		SaboteurControls.GroundAction.FLYING_KICK
	)


func test_still_fire_on_ladder_is_still_punch() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, false, true, true, false),
		SaboteurControls.GroundAction.PUNCH
	)


func test_no_taps_is_none() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(true, false, false, false, false),
		SaboteurControls.GroundAction.NONE
	)


func test_fire_is_a_low_punch_only_while_ducking() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, false, true, false, false, false, true),
		SaboteurControls.GroundAction.CROUCH_PUNCH
	)
	assert_eq(
		SaboteurControls.resolve_ground(false, false, true, false, false, false, false),
		SaboteurControls.GroundAction.PUNCH
	)


func test_moving_up_and_fire_is_the_somersault_either_tap_order() -> void:
	# UP is the fresh tap.
	assert_eq(
		SaboteurControls.resolve_ground(true, true, false, false, false, true),
		SaboteurControls.GroundAction.SOMERSAULT
	)
	# FIRE is the fresh tap.
	assert_eq(
		SaboteurControls.resolve_ground(true, false, true, false, false, true),
		SaboteurControls.GroundAction.SOMERSAULT
	)


func test_somersault_needs_movement_a_fresh_tap_and_a_free_lift() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(false, true, false, false, false, true),
		SaboteurControls.GroundAction.STAND_KICK,
		"standing still is a kick, not a long jump"
	)
	assert_eq(
		SaboteurControls.resolve_ground(true, false, false, false, false, true),
		SaboteurControls.GroundAction.NONE,
		"both buttons down but neither newly pressed starts nothing"
	)
	assert_eq(
		SaboteurControls.resolve_ground(true, true, false, false, true, true),
		SaboteurControls.GroundAction.NONE,
		"a usable lift still outranks the chord"
	)


func test_inlay_rows_are_unchanged_without_the_new_arguments() -> void:
	# The 1987 table is the default: callers that pass only the original five
	# arguments must see exactly the original five outcomes.
	assert_eq(
		SaboteurControls.resolve_ground(true, true, false, false, false),
		SaboteurControls.GroundAction.RUNNING_JUMP
	)
	assert_eq(
		SaboteurControls.resolve_ground(true, false, true, false, false),
		SaboteurControls.GroundAction.FLYING_KICK
	)
	assert_eq(
		SaboteurControls.resolve_ground(false, false, true, false, false),
		SaboteurControls.GroundAction.PUNCH
	)


func test_crouch_only_when_still() -> void:
	assert_true(SaboteurControls.should_crouch(false, true, false))
	assert_false(SaboteurControls.should_crouch(true, true, false))
	assert_false(SaboteurControls.should_crouch(false, true, true))
	assert_false(SaboteurControls.should_crouch(false, false, false))


func test_crawl_when_down_and_moving() -> void:
	assert_true(SaboteurControls.should_crawl(true, true, false))
	assert_false(SaboteurControls.should_crawl(false, true, false))
	assert_false(SaboteurControls.should_crawl(true, true, true))
	assert_false(SaboteurControls.should_crawl(true, false, false))


func test_crawling_fire_is_a_low_punch() -> void:
	assert_eq(
		SaboteurControls.resolve_ground(true, false, true, false, false, false, true),
		SaboteurControls.GroundAction.CROUCH_PUNCH
	)


func test_space_is_only_on_jump_not_move_up() -> void:
	for event in InputMap.action_get_events("move_up"):
		var key := event as InputEventKey
		if key != null:
			assert_ne(key.physical_keycode, KEY_SPACE)
	var space_on_jump := false
	for event in InputMap.action_get_events("jump"):
		var key := event as InputEventKey
		if key != null and key.physical_keycode == KEY_SPACE:
			space_on_jump = true
	assert_true(space_on_jump)


func test_jump_action_counts_as_up() -> void:
	assert_false(SaboteurControls.wants_up())
	Input.action_press("jump")
	assert_true(SaboteurControls.wants_up())
	assert_eq(SaboteurControls.climb_axis(), -1.0)
	assert_false(Input.is_action_pressed("move_up"), "Space lives only on jump")


func test_move_up_and_down_set_climb_axis() -> void:
	Input.action_press("move_up")
	assert_eq(SaboteurControls.climb_axis(), -1.0)
	Input.action_release("move_up")
	Input.action_press("move_down")
	assert_eq(SaboteurControls.climb_axis(), 1.0)
