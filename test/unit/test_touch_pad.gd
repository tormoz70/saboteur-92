extends GutTest
## 8-way pad maps a finger to movement chords without dropping a shared axis.


const ChordPad := preload("res://scripts/ui/chord_touch_button.gd")
const OctantPad := preload("res://scripts/ui/octant_touch_pad.gd")


func after_each() -> void:
	ChordPad.reset_holds()
	for action in ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]:
		if Input.is_action_pressed(action):
			Input.action_release(action)


func test_two_buttons_sharing_an_action_keep_it_held() -> void:
	ChordPad.retain(&"move_left")
	ChordPad.retain(&"move_left")
	ChordPad.retain(&"move_up")
	assert_true(Input.is_action_pressed("move_left"))
	assert_true(Input.is_action_pressed("move_up"))
	ChordPad.drop(&"move_left")
	assert_true(Input.is_action_pressed("move_left"), "still held by the other pad button")
	assert_true(Input.is_action_pressed("move_up"))
	ChordPad.drop(&"move_left")
	ChordPad.drop(&"move_up")
	assert_false(Input.is_action_pressed("move_left"))
	assert_false(Input.is_action_pressed("move_up"))


func test_diagonal_pad_has_jump_and_crawl_chords() -> void:
	assert_eq(OctantPad.chord_for(7), PackedStringArray(["move_right", "move_up"]))
	assert_eq(OctantPad.chord_for(5), PackedStringArray(["move_left", "move_up"]))
	assert_eq(OctantPad.chord_for(1), PackedStringArray(["move_right", "move_down"]))
	assert_eq(OctantPad.chord_for(3), PackedStringArray(["move_left", "move_down"]))
	var packed: PackedScene = load("res://scenes/ui/touch_controls.tscn")
	var ui: CanvasLayer = packed.instantiate()
	add_child_autofree(ui)
	assert_true(ui.get_node("Root/LeftPad") is OctantTouchPad)
	var left: Control = ui.get_node("Root/LeftPad")
	var right: Control = ui.get_node("Root/RightPad")
	assert_lt(left.offset_left, 0.0, "D-pad hangs off the left of the viewport")
	assert_gt(left.offset_right, 80.0, "the right half of the disc stays on-screen")
	assert_gt(right.offset_right, -24.0, "HIT/JMP should sit on the right edge")


func test_octant_from_vec_matches_compass() -> void:
	var pad: OctantTouchPad = _make_pad()
	assert_eq(pad.octant_from_vec(Vector2.RIGHT), 0)
	assert_eq(pad.octant_from_vec(Vector2.DOWN), 2)
	assert_eq(pad.octant_from_vec(Vector2.LEFT), 4)
	assert_eq(pad.octant_from_vec(Vector2.UP), 6)
	assert_eq(pad.octant_from_vec(Vector2(1, 1)), 1)
	assert_eq(pad.octant_from_vec(Vector2(-1, 1)), 3)
	assert_eq(pad.octant_from_vec(Vector2(-1, -1)), 5)
	assert_eq(pad.octant_from_vec(Vector2(1, -1)), 7)


func test_right_press_holds_move_right() -> void:
	var pad: OctantTouchPad = _make_pad()
	_touch(pad, pad.size * 0.5 + Vector2(80, 0), true)
	assert_true(Input.is_action_pressed("move_right"))
	assert_false(Input.is_action_pressed("move_up"))
	_touch(pad, pad.size * 0.5 + Vector2(80, 0), false)
	assert_false(Input.is_action_pressed("move_right"))


func test_hub_press_is_not_a_dead_zone() -> void:
	var pad: OctantTouchPad = _make_pad()
	_touch(pad, pad.size * 0.5 + Vector2(20, 0), true)
	assert_true(Input.is_action_pressed("move_right"), "pie slices start at the center")
	pad.release_finger()


func test_slide_from_left_onto_jump_left_keeps_move_left() -> void:
	var pad: OctantTouchPad = _make_pad()
	_touch(pad, pad.size * 0.5 + Vector2(-80, 0), true)
	assert_true(Input.is_action_pressed("move_left"))
	assert_false(Input.is_action_pressed("move_up"))
	_drag(pad, pad.size * 0.5 + Vector2(-60, -60))
	assert_true(Input.is_action_pressed("move_left"), "shared axis stays held across octants")
	assert_true(Input.is_action_pressed("move_up"))
	pad.release_finger()
	assert_false(Input.is_action_pressed("move_left"))
	assert_false(Input.is_action_pressed("move_up"))


func test_tap_outside_the_disc_does_nothing() -> void:
	var pad: OctantTouchPad = _make_pad()
	_touch(pad, Vector2(-40, -40), true)
	assert_false(Input.is_action_pressed("move_left"))
	assert_false(Input.is_action_pressed("move_right"))
	assert_false(Input.is_action_pressed("move_up"))
	assert_false(Input.is_action_pressed("move_down"))


func _make_pad() -> OctantTouchPad:
	var pad: OctantTouchPad = OctantPad.new()
	pad.size = Vector2(296, 296)
	add_child_autofree(pad)
	return pad


func _touch(pad: OctantTouchPad, local_pos: Vector2, pressed: bool) -> void:
	var ev := InputEventScreenTouch.new()
	ev.index = 0
	ev.pressed = pressed
	ev.position = pad.global_position + local_pos
	pad._input(ev)


func _drag(pad: OctantTouchPad, local_pos: Vector2) -> void:
	var ev := InputEventScreenDrag.new()
	ev.index = 0
	ev.position = pad.global_position + local_pos
	pad._input(ev)
