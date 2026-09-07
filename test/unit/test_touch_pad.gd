extends GutTest
## Shared hold counts so 8-way pad chords do not drop a direction mid-slide.

const ChordPad := preload("res://scripts/ui/chord_touch_button.gd")


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
	var packed: PackedScene = load("res://scenes/ui/touch_controls.tscn")
	var ui: CanvasLayer = packed.instantiate()
	add_child_autofree(ui)
	var pad: Node = ui.get_node("Root/LeftPad")
	assert_eq(pad.get_node("btnJumpLeft").chord, PackedStringArray(["move_left", "move_up"]))
	assert_eq(pad.get_node("btnJumpRight").chord, PackedStringArray(["move_right", "move_up"]))
	assert_eq(pad.get_node("btnCrawlLeft").chord, PackedStringArray(["move_left", "move_down"]))
	assert_eq(pad.get_node("btnCrawlRight").chord, PackedStringArray(["move_right", "move_down"]))
	assert_eq(pad.get_child_count(), 8)
