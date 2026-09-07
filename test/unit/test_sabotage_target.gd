extends GutTest
## Tint follows EventBus; death with lives left must clear it without a scene reload.


func after_each() -> void:
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func _spawn_target() -> Area2D:
	var target: Area2D = load("res://scripts/items/sabotage_target.gd").new()
	add_child_autofree(target)
	return target


func test_ready_starts_untinted() -> void:
	var target := _spawn_target()
	await get_tree().process_frame
	assert_eq(target.modulate, Color(1.0, 1.0, 1.0, 0.7))


func test_bomb_planted_tints_red() -> void:
	var target := _spawn_target()
	await get_tree().process_frame
	GameManager.has_bomb = true
	EventBus.bomb_planted.emit()
	assert_eq(target.modulate, Color(1.0, 0.3, 0.3))


func test_player_died_clears_tint_after_inventory_reset() -> void:
	var target := _spawn_target()
	await get_tree().process_frame
	GameManager.has_bomb = true
	EventBus.bomb_planted.emit()
	assert_true(GameManager.bomb_planted)
	GameManager.lose_mission()
	assert_false(GameManager.bomb_planted)
	assert_eq(GameManager.lives, 2)
	assert_eq(target.modulate, Color(1.0, 1.0, 1.0, 0.7))
