extends GutTest
## Lab mission: crate codes, locked lift, interlock, alarm fuse.


func after_each() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func test_three_markers_enable_lift_code() -> void:
	GameManager.note_code("02")
	GameManager.note_code("11")
	assert_false(GameManager.has_lift_code)
	GameManager.note_code("06")
	assert_true(GameManager.has_lift_code)


func test_marker_seen_emits_event() -> void:
	watch_signals(EventBus)
	GameManager.note_code("02")
	assert_signal_emitted(EventBus, "marker_seen")
	assert_signal_emit_count(EventBus, "marker_seen", 1)


func test_locked_lift_requires_code() -> void:
	var lift: Lift = load("res://scripts/world/lift.gd").new()
	lift.requires_lift_code = true
	lift.setup(0.0, 200.0, 48.0)
	lift.global_position = Vector2(100.0, 100.0)
	add_child_autofree(lift)
	var player := CharacterBody2D.new()
	player.add_to_group("player")
	player.global_position = Vector2(76.0, 100.0)
	add_child_autofree(player)
	assert_false(lift.start_ride(player, 1))
	GameManager.note_code("02")
	GameManager.note_code("06")
	GameManager.note_code("11")
	assert_true(lift.start_ride(player, 1))


func test_bookcase_passage_needs_crouch() -> void:
	var passage: Area2D = load("res://scripts/world/bookcase_passage.gd").new()
	passage.dest_x = 500.0
	passage.dest_y = 600.0
	passage.need_crouch = true
	add_child_autofree(passage)
	var mock := GDScript.new()
	mock.source_code = "extends CharacterBody2D\nvar low := false\nfunc is_low_stance() -> bool:\n\treturn low"
	assert_eq(mock.reload(), OK)
	var player := CharacterBody2D.new()
	player.set_script(mock)
	player.add_to_group("player")
	player.global_position = Vector2(100.0, 100.0)
	player.set("low", false)
	add_child_autofree(player)
	passage._on_body_entered(player)
	assert_eq(player.global_position, Vector2(100.0, 100.0))
	player.set("low", true)
	passage._on_body_entered(player)
	assert_eq(player.global_position, Vector2(500.0, 600.0))


func test_interlock_skips_document_on_console() -> void:
	var target: Area2D = load("res://scripts/items/sabotage_target.gd").new()
	add_child_autofree(target)
	var player := CharacterBody2D.new()
	player.add_to_group("player")
	add_child_autofree(player)
	GameManager.has_bomb = true
	GameManager.cut_interlock()
	target._on_body_entered(player)
	assert_true(GameManager.bomb_planted)


func test_alarm_shortens_fuse_cap() -> void:
	GameManager.bomb_fuse_time = 50.0
	GameManager.has_bomb = true
	GameManager._on_bomb_planted()
	assert_eq(GameManager.bomb_timer, 50.0)
	GameManager.raise_alarm()
	assert_eq(GameManager.bomb_fuse_time, 35.0)
	assert_almost_eq(GameManager.bomb_timer, 35.0, 0.0001)
	assert_true(GameManager.alarmed)


func test_reset_inventory_clears_mission_progress() -> void:
	GameManager.note_code("02")
	GameManager.cut_interlock()
	GameManager.raise_alarm()
	GameManager.reset_inventory()
	assert_false(GameManager.has_lift_code)
	assert_false(GameManager.interlock_cut)
	assert_false(GameManager.alarmed)
