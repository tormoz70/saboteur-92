extends GutTest
## AudioManager: pool, unknown names, EventBus wiring for key mission SFX.

const PLAYER_SCENE := preload("res://scenes/player/player.tscn")


func before_each() -> void:
	AudioManager.reset_play_counts()
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func after_each() -> void:
	AudioManager.reset_play_counts()
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0
	AudioManager.play_music(false)


func test_play_sfx_by_name_increments_count() -> void:
	AudioManager.play_sfx("punch")
	assert_eq(AudioManager.last_sfx, "punch")
	assert_eq(AudioManager.play_counts.get("punch", 0), 1)


func test_unknown_sfx_name_does_not_crash() -> void:
	AudioManager.play_sfx("no_such_effect_xyz")
	assert_eq(AudioManager.last_sfx, "")
	assert_eq(AudioManager.play_counts.size(), 0)


func test_pool_does_not_grow_past_limit() -> void:
	var before := AudioManager.get_pool_size()
	assert_eq(before, 8)
	for _i in 40:
		AudioManager.play_sfx("step")
	assert_eq(AudioManager.get_pool_size(), before)
	assert_eq(int(AudioManager.play_counts.get("step", 0)), 40)


func test_item_collected_plays_pickup() -> void:
	EventBus.item_collected.emit("key")
	assert_eq(AudioManager.play_counts.get("pickup", 0), 1)


func test_player_died_plays_death() -> void:
	EventBus.player_died.emit()
	assert_eq(AudioManager.play_counts.get("death", 0), 1)


func test_mission_complete_plays_win() -> void:
	EventBus.mission_complete.emit()
	assert_eq(AudioManager.play_counts.get("win", 0), 1)


func test_alarm_raised_plays_alarm() -> void:
	EventBus.alarm_raised.emit()
	assert_eq(AudioManager.play_counts.get("alarm", 0), 1)


func test_bomb_planted_plays_fuse_tick_on_process() -> void:
	GameManager.has_bomb = true
	EventBus.bomb_planted.emit()
	assert_true(GameManager.bomb_planted)
	AudioManager._process(1.05)
	assert_eq(AudioManager.play_counts.get("fuse_tick", 0), 1)


func test_player_punch_plays_sfx() -> void:
	var player: Player = PLAYER_SCENE.instantiate()
	add_child_autofree(player)
	await get_tree().process_frame
	AudioManager.reset_play_counts()
	player._start_punch()
	assert_eq(AudioManager.play_counts.get("punch", 0), 1)


func test_player_somersault_plays_sfx() -> void:
	var player: Player = PLAYER_SCENE.instantiate()
	add_child_autofree(player)
	await get_tree().process_frame
	AudioManager.reset_play_counts()
	player._start_somersault()
	assert_eq(AudioManager.play_counts.get("somersault", 0), 1)
