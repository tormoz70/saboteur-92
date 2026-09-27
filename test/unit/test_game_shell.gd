extends GutTest
## game.tscn wiring: the real level with HUD, touch pad, pause and results.

const GAME_SCENE := preload("res://scenes/game.tscn")
const TEMP_RECORDS := "user://test_records_shell_tmp.cfg"

var _game: Node


func before_each() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0
	_remove_temp()
	_game = GAME_SCENE.instantiate()
	_game.get_node("ResultScreen").records_path = TEMP_RECORDS
	add_child_autofree(_game)
	while not _game.level.world_loaded:
		await get_tree().process_frame


func after_each() -> void:
	Input.action_release("move_right")
	get_tree().paused = false
	AudioManager.set_paused(false)
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0
	AudioManager.play_music(false)
	_remove_temp()


func test_level_ready_starts_the_clock_and_lifts_the_curtain() -> void:
	assert_false(_game.loading.visible)
	assert_true(_game.pause_menu.game_ready)
	assert_true(GameManager.clock_running)
	await _frames(3)
	assert_gt(GameManager.mission_time, 0.0)


func test_pause_button_and_focus_loss_freeze_the_run() -> void:
	var player: Node2D = _game.level.player
	Input.action_press("move_right")
	await _frames(10)
	_game.hud.pause_pressed.emit()
	assert_true(get_tree().paused)
	assert_false(_game.touch_controls.visible, "pad hidden under the pause menu")
	var pos := player.global_position
	var clock := GameManager.mission_time
	await _frames(20)
	assert_eq(player.global_position, pos, "Nina does not move while paused")
	assert_eq(GameManager.mission_time, clock, "mission clock frozen")
	_game.pause_menu.resume_game()
	assert_true(_game.touch_controls.visible)
	await _frames(5)
	assert_gt(GameManager.mission_time, clock)
	_game.pause_menu.autopause_enabled = true
	_game.propagate_notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	assert_true(get_tree().paused, "focus loss pauses the game")
	pos = player.global_position
	clock = GameManager.mission_time
	await _frames(20)
	assert_eq(player.global_position, pos)
	assert_eq(GameManager.mission_time, clock)


func test_win_shows_results_and_saves_the_record() -> void:
	GameManager.mission_time = 88.4
	GameManager.win_mission()
	var result: CanvasLayer = _game.result_screen
	assert_true(result.visible)
	assert_false(_game.touch_controls.visible)
	assert_eq(result.title_label.text, "MISSION COMPLETE")
	assert_eq(result.time_value.text, "01:28.4")
	assert_eq(result.alarm_value.text, "NOT RAISED")
	assert_true(result.retry_button.visible and result.main_menu_button.visible)
	var best := MissionRecords.load_best(TEMP_RECORDS)
	assert_almost_eq(float(best["time"]), 88.4, 0.01)
	assert_eq(int(best["score"]), GameManager.score)


func test_demo_win_does_not_touch_records() -> void:
	GameManager.demo_mode = true
	GameManager.mission_time = 30.0
	GameManager.win_mission()
	assert_true(_game.result_screen.visible)
	assert_false(FileAccess.file_exists(TEMP_RECORDS))


func test_game_over_offers_retry_and_main_menu() -> void:
	GameManager.raise_alarm()
	GameManager.fail_mission("The complex collapsed")
	var result: CanvasLayer = _game.result_screen
	assert_true(result.visible)
	assert_eq(result.title_label.text, "THE COMPLEX COLLAPSED")
	assert_eq(result.alarm_value.text, "RAISED")
	assert_true(result.retry_button.visible and result.main_menu_button.visible)
	assert_false(FileAccess.file_exists(TEMP_RECORDS), "a loss is not a record")
	_game.pause_menu.pause_game()
	assert_false(get_tree().paused, "no pause over the result screen")


func _frames(count: int) -> void:
	for _i in count:
		await get_tree().process_frame


func _remove_temp() -> void:
	if FileAccess.file_exists(TEMP_RECORDS):
		DirAccess.remove_absolute(TEMP_RECORDS)
