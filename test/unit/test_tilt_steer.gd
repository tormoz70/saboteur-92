extends GutTest
## Tilt mapping is a pure function; move_axis prefers buttons over the sensor.


func after_each() -> void:
	TiltSteer.enabled = false
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0
	Input.action_release("move_left")
	Input.action_release("move_right")


func test_landscape_left_edge_down_walks_left() -> void:
	var acc := Vector3(0.0, 3.0, 0.0)
	var axis := TiltSteer.axis_from_accelerometer(acc, TiltSteer.Orientation.LANDSCAPE)
	assert_eq(axis, -1.0)


func test_landscape_right_edge_down_walks_right() -> void:
	var acc := Vector3(0.0, -3.0, 0.0)
	var axis := TiltSteer.axis_from_accelerometer(acc, TiltSteer.Orientation.LANDSCAPE)
	assert_eq(axis, 1.0)


func test_deadzone_is_neutral() -> void:
	var acc := Vector3(0.0, 0.4, 0.0)
	var axis := TiltSteer.axis_from_accelerometer(acc, TiltSteer.Orientation.LANDSCAPE)
	assert_eq(axis, 0.0)


func test_reverse_landscape_flips_the_same_roll() -> void:
	var acc := Vector3(0.0, 3.0, 0.0)
	var axis := TiltSteer.axis_from_accelerometer(
		acc, TiltSteer.Orientation.REVERSE_LANDSCAPE
	)
	assert_eq(axis, 1.0)


func test_portrait_uses_device_x() -> void:
	var acc := Vector3(-3.0, 0.0, 0.0)
	var axis := TiltSteer.axis_from_accelerometer(acc, TiltSteer.Orientation.PORTRAIT)
	assert_eq(axis, -1.0)


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
