extends GutTest
## Pause menu: tree pause freezes the mission clock and fuse, autopause on
## app notifications, back/Esc routing, and demo flags skipping the title.

const PAUSE_SCENE := preload("res://scenes/ui/pause_menu.tscn")
const SETTINGS_SCENE := preload("res://scenes/ui/settings_menu.tscn")

var _menu: CanvasLayer


func before_each() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0
	AudioManager.reset_play_counts()
	_menu = PAUSE_SCENE.instantiate()
	add_child_autofree(_menu)
	_menu.game_ready = true


func after_each() -> void:
	get_tree().paused = false
	AudioManager.set_paused(false)
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0
	AudioManager.reset_play_counts()
	AudioManager.play_music(false)


func test_pause_freezes_mission_clock_fuse_and_tick() -> void:
	GameManager.start_clock()
	GameManager.has_bomb = true
	EventBus.bomb_planted.emit()
	await _frames(3)
	_menu.pause_game()
	assert_true(get_tree().paused)
	assert_true(AudioManager.is_paused(), "music held, not restarted")
	var clock := GameManager.mission_time
	var fuse := GameManager.bomb_timer
	AudioManager.reset_play_counts()
	AudioManager.play_sfx("punch")
	assert_eq(AudioManager.play_counts.size(), 0, "no new effects on pause")
	# SceneTreeTimer defaults to process_always, so it runs through the pause.
	await get_tree().create_timer(AudioManager.FUSE_TICK_SEC + 0.3).timeout
	assert_eq(GameManager.mission_time, clock, "mission clock stopped")
	assert_eq(GameManager.bomb_timer, fuse, "fuse stopped")
	assert_eq(int(AudioManager.play_counts.get("fuse_tick", 0)), 0, "no fuse tick on pause")
	_menu.resume_game()
	assert_false(get_tree().paused)
	assert_false(AudioManager.is_paused())
	await _frames(5)
	assert_gt(GameManager.mission_time, clock, "clock runs again")
	assert_lt(GameManager.bomb_timer, fuse, "fuse runs again")


func test_focus_out_autopauses() -> void:
	_menu.autopause_enabled = true
	_menu.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	assert_true(get_tree().paused)
	assert_true(_menu.is_paused)
	assert_true(_menu.visible, "pause menu is shown")


func test_app_paused_autopauses() -> void:
	_menu.autopause_enabled = true
	_menu.notification(Node.NOTIFICATION_APPLICATION_PAUSED)
	assert_true(get_tree().paused)
	assert_true(_menu.is_paused)


func test_headless_run_never_autopauses() -> void:
	assert_false(_menu.autopause_enabled, "off under the headless display server")
	_menu.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	assert_false(get_tree().paused)


func test_no_pause_before_the_level_is_ready() -> void:
	_menu.game_ready = false
	_menu.pause_game()
	assert_false(get_tree().paused)


func test_no_pause_in_demo_mode() -> void:
	GameManager.demo_mode = true
	_menu.autopause_enabled = true
	_menu.notification(Node.NOTIFICATION_APPLICATION_FOCUS_OUT)
	assert_false(get_tree().paused)


func test_no_pause_once_the_mission_is_over() -> void:
	GameManager.win_mission()
	_menu.pause_game()
	assert_false(get_tree().paused)


func test_back_toggles_pause() -> void:
	_menu.handle_back()
	assert_true(_menu.is_paused)
	_menu.handle_back()
	assert_false(_menu.is_paused)
	assert_false(get_tree().paused)


func test_ui_cancel_pauses() -> void:
	var esc := InputEventAction.new()
	esc.action = "ui_cancel"
	esc.pressed = true
	_menu._unhandled_input(esc)
	assert_true(_menu.is_paused)


func test_back_closes_settings_before_resuming() -> void:
	var settings: CanvasLayer = SETTINGS_SCENE.instantiate()
	add_child_autofree(settings)
	_menu.settings_menu = settings
	settings.closed.connect(_menu.return_from_settings)
	_menu.pause_game()
	_menu._on_settings_pressed()
	settings.open()
	assert_false(_menu.panel.visible)
	_menu.handle_back()
	assert_false(settings.is_open(), "first back closes settings")
	assert_true(_menu.is_paused, "and keeps the game paused")
	assert_true(_menu.panel.visible, "pause panel is back")
	assert_eq(get_viewport().gui_get_focus_owner(), _menu.settings_button, "focus returns")
	_menu.handle_back()
	assert_false(_menu.is_paused)


func test_demo_flags_skip_the_title() -> void:
	for arg in ["--demo", "--demo-fuse", "--demo-tilt", "--demo-maze", "--demo-explore"]:
		assert_true(TitleScreen.wants_demo(PackedStringArray([arg])), arg)
	assert_false(TitleScreen.wants_demo(PackedStringArray()))
	assert_false(TitleScreen.wants_demo(PackedStringArray(["--verbose"])))


func _frames(count: int) -> void:
	for _i in count:
		await get_tree().process_frame
