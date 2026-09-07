extends GutTest
## GameManager is an autoload. Tests reset it in after_each so they cannot leak.


func after_each() -> void:
	_reset_gm()


func _reset_gm() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func test_starts_playing_with_three_lives_and_empty_inventory() -> void:
	assert_eq(GameManager.state, GameManager.GameState.PLAYING)
	assert_eq(GameManager.lives, 3)
	assert_eq(GameManager.score, 0)
	assert_false(GameManager.has_key)
	assert_false(GameManager.has_document)
	assert_false(GameManager.has_bomb)
	assert_false(GameManager.bomb_planted)
	assert_eq(GameManager.bomb_timer, 0.0)


func test_collecting_items_sets_flags_and_adds_score() -> void:
	GameManager._on_item_collected("key")
	GameManager._on_item_collected("document")
	GameManager._on_item_collected("bomb")
	assert_true(GameManager.has_key)
	assert_true(GameManager.has_document)
	assert_true(GameManager.has_bomb)
	assert_eq(GameManager.score, 150)


func test_reset_inventory_clears_pickups_and_fuse() -> void:
	GameManager.has_key = true
	GameManager.has_document = true
	GameManager.has_bomb = true
	GameManager.bomb_planted = true
	GameManager.bomb_timer = 12.0
	GameManager.reset_inventory()
	assert_false(GameManager.has_key)
	assert_false(GameManager.has_document)
	assert_false(GameManager.has_bomb)
	assert_false(GameManager.bomb_planted)
	assert_eq(GameManager.bomb_timer, 0.0)


func test_win_mission_adds_escape_bonus_and_is_idempotent() -> void:
	GameManager.score = 150
	GameManager.win_mission()
	assert_eq(GameManager.state, GameManager.GameState.WON)
	assert_eq(GameManager.score, 150 + GameManager.ESCAPE_BONUS)
	GameManager.win_mission()
	assert_eq(GameManager.score, 150 + GameManager.ESCAPE_BONUS)


func test_lose_mission_decrements_lives_then_game_over() -> void:
	GameManager.has_key = true
	GameManager.lose_mission()
	assert_eq(GameManager.lives, 2)
	assert_eq(GameManager.state, GameManager.GameState.PLAYING)
	assert_false(GameManager.has_key)
	GameManager.lose_mission()
	GameManager.lose_mission()
	assert_eq(GameManager.lives, 0)
	assert_eq(GameManager.state, GameManager.GameState.LOST)
	assert_eq(GameManager.fail_reason, "Game Over")


func test_fail_mission_zeros_lives() -> void:
	GameManager.fail_mission("The bomb exploded")
	assert_eq(GameManager.state, GameManager.GameState.LOST)
	assert_eq(GameManager.lives, 0)
	assert_eq(GameManager.fail_reason, "The bomb exploded")


func test_planting_starts_fuse_and_process_expires_it() -> void:
	GameManager.has_bomb = true
	GameManager.bomb_fuse_time = 0.5
	GameManager._on_bomb_planted()
	assert_true(GameManager.bomb_planted)
	assert_false(GameManager.has_bomb)
	assert_eq(GameManager.bomb_timer, 0.5)
	GameManager._process(0.4)
	assert_eq(GameManager.state, GameManager.GameState.PLAYING)
	assert_almost_eq(GameManager.bomb_timer, 0.1, 0.0001)
	GameManager._process(0.2)
	assert_eq(GameManager.state, GameManager.GameState.LOST)
	assert_eq(GameManager.bomb_timer, 0.0)
	assert_eq(GameManager.fail_reason, "The bomb exploded")


func test_reset_run_state_restores_a_fresh_mission() -> void:
	GameManager.state = GameManager.GameState.LOST
	GameManager.lives = 0
	GameManager.score = 999
	GameManager.has_key = true
	GameManager.demo_mode = true
	GameManager.fail_reason = "Game Over"
	GameManager.reset_run_state()
	assert_eq(GameManager.state, GameManager.GameState.PLAYING)
	assert_eq(GameManager.lives, 3)
	assert_eq(GameManager.score, 0)
	assert_false(GameManager.has_key)
	assert_false(GameManager.demo_mode)
	assert_eq(GameManager.fail_reason, "")


func test_killing_an_enemy_adds_one_hundred() -> void:
	var enemy := Node.new()
	GameManager._on_enemy_killed(enemy)
	assert_eq(GameManager.score, 100)
	enemy.free()


func test_event_bus_item_collected_reaches_game_manager() -> void:
	EventBus.item_collected.emit("key")
	assert_true(GameManager.has_key, "GameManager._ready must stay subscribed")
	assert_eq(GameManager.score, 50)


func test_event_bus_bomb_planted_reaches_game_manager() -> void:
	GameManager.has_bomb = true
	EventBus.bomb_planted.emit()
	assert_true(GameManager.bomb_planted, "GameManager._ready must stay subscribed")
	assert_false(GameManager.has_bomb)
	assert_eq(GameManager.bomb_timer, GameManager.bomb_fuse_time)
