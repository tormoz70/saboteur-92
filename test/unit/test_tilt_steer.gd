extends GutTest
## Tilt mapping and hysteresis are pure functions; move_axis prefers buttons.


func after_each() -> void:
	TiltSteer.enabled = false
	Input.set_gravity(Vector3.ZERO)
	Input.set_accelerometer(Vector3.ZERO)
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0
	Input.action_release("move_left")
	Input.action_release("move_right")


func test_screen_left_edge_down_walks_left() -> void:
	# Godot hands over gravity already rotated into screen space, so the
	# horizontal component is x whatever the device rotation is.
	var tilt := TiltSteer.screen_tilt(Vector3(-9.0, -3.0, 0.0))
	assert_eq(TiltSteer.axis_from_tilt(tilt, 0.0), -1.0)


func test_screen_right_edge_down_walks_right() -> void:
	var tilt := TiltSteer.screen_tilt(Vector3(9.0, -3.0, 0.0))
	assert_eq(TiltSteer.axis_from_tilt(tilt, 0.0), 1.0)


func test_pitching_the_phone_does_not_steer() -> void:
	# Leaning the top edge away only moves gravity on the screen-vertical
	# axis; that used to be the axis the walk direction was read from.
	var tilt := TiltSteer.screen_tilt(Vector3(0.0, -9.0, 3.0))
	assert_eq(TiltSteer.axis_from_tilt(tilt, 0.0), 0.0)


func test_deadzone_is_neutral() -> void:
	assert_eq(TiltSteer.axis_from_tilt(0.4, 0.0), 0.0)


func test_small_tilt_keeps_a_walk_that_already_started() -> void:
	# Hysteresis: past the engage angle to start, past the smaller hold angle
	# to keep going, so a shaking hand near the edge does not stutter.
	assert_eq(TiltSteer.axis_from_tilt(1.5, 1.0), 1.0)
	assert_eq(TiltSteer.axis_from_tilt(1.5, 0.0), 0.0)
	assert_eq(TiltSteer.axis_from_tilt(0.9, 1.0), 0.0)


func test_tilting_the_other_way_needs_the_engage_angle() -> void:
	assert_eq(TiltSteer.axis_from_tilt(-1.5, 1.0), 0.0)
	assert_eq(TiltSteer.axis_from_tilt(-2.5, 1.0), -1.0)


func test_move_axis_is_zero_when_tilt_is_off() -> void:
	TiltSteer.enabled = false
	assert_eq(TiltSteer.move_axis(), 0.0)


func test_buttons_override_tilt() -> void:
	TiltSteer.enabled = true
	Input.action_press("move_right")
	assert_gt(TiltSteer.move_axis(), 0.0)
	Input.action_release("move_right")
	Input.action_press("move_left")
	assert_lt(TiltSteer.move_axis(), 0.0)


func test_demo_mode_ignores_tilt() -> void:
	TiltSteer.enabled = true
	GameManager.demo_mode = true
	assert_eq(TiltSteer.move_axis(), 0.0)


func test_missing_sensor_is_reported_after_the_grace_period() -> void:
	TiltSteer.enabled = true
	assert_false(TiltSteer.sensor_missing, "no verdict before the grace period")
	# Desktop and CI have no accelerometer, so every read is Vector3.ZERO.
	TiltSteer._physics_process(TiltSteer.SENSOR_GRACE + 0.1)
	assert_true(TiltSteer.sensor_missing)
	assert_eq(TiltSteer.move_axis(), 0.0)
	TiltSteer.enabled = false
	assert_false(TiltSteer.sensor_missing, "switching tilt off clears the warning")


func test_a_tilted_phone_steers_the_walk_axis() -> void:
	# Input.set_gravity feeds the same path a real phone's sensor does, so this
	# covers reading, smoothing and the walk axis together.
	TiltSteer.enabled = true
	_hold_phone(Vector3(-9.0, -3.0, 0.0))
	assert_lt(TiltSteer.move_axis(), 0.0, "screen-left edge down walks left")
	_hold_phone(Vector3(9.0, -3.0, 0.0))
	assert_gt(TiltSteer.move_axis(), 0.0, "screen-right edge down walks right")
	_hold_phone(Vector3(0.0, -9.8, 0.0))
	assert_eq(TiltSteer.move_axis(), 0.0, "held level, nobody walks")
	assert_false(TiltSteer.sensor_missing, "a reporting sensor is not a missing one")


func test_switching_tilt_on_calibrates_the_current_hold() -> void:
	Input.set_gravity(Vector3(-3.0, -9.0, 0.0))
	TiltSteer.enabled = true
	_settle_tilt()
	assert_eq(TiltSteer.move_axis(), 0.0, "the angle it was switched on at is neutral")
	_hold_phone(Vector3(2.0, -9.0, 0.0))
	assert_gt(TiltSteer.move_axis(), 0.0, "and steering is measured from there")


func test_accelerometer_only_phones_still_steer() -> void:
	TiltSteer.enabled = true
	Input.set_accelerometer(Vector3(-9.0, -3.0, 0.0))
	_settle_tilt()
	assert_lt(TiltSteer.move_axis(), 0.0, "no gravity sensor, so read the accelerometer")


func _hold_phone(gravity: Vector3) -> void:
	Input.set_gravity(gravity)
	_settle_tilt()


func _settle_tilt() -> void:
	# The reading is low-passed, so give it a few frames to arrive.
	for _i in 30:
		TiltSteer._physics_process(1.0 / 60.0)


func test_accelerometer_project_settings_are_on() -> void:
	# Android only registers its sensor listener when these are true; with
	# them off Input.get_accelerometer() is always Vector3.ZERO on a phone.
	assert_true(bool(ProjectSettings.get_setting("input_devices/sensors/enable_accelerometer")))
	assert_true(bool(ProjectSettings.get_setting("input_devices/sensors/enable_gravity")))
