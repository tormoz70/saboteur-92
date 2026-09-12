extends GutTest
## Full level is playable from TileMapLayers + greedy-merged physics.


func after_each() -> void:
	if Input.is_action_pressed("move_left"):
		Input.action_release("move_left")
	GameManager.reset_run_state()
	GameManager.bomb_fuse_time = 50.0


func test_level_tilemaps_have_used_cells() -> void:
	var packed: PackedScene = load("res://scenes/levels/level_01.tscn")
	var level: Node2D = packed.instantiate()
	add_child_autofree(level)
	await get_tree().process_frame
	var sky := level.get_node("Sky") as TileMapLayer
	var collision := level.get_node("CollisionLayer") as TileMapLayer
	assert_gt(sky.get_used_cells().size(), 0, "sky tiles")
	assert_gt(collision.get_used_cells().size(), 0, "collision tiles")
	assert_not_null(level.get_node_or_null("World/Solids"))
	assert_not_null(level.get_node_or_null("World/Ladders"))
	assert_not_null(level.get_node_or_null("World/Lifts"))
	assert_gt(level.get_node("World/Solids").get_child_count(), 0)
	assert_gt(level.get_node("World/Ladders").get_child_count(), 0)
	assert_gt(level.get_node("World/Lifts").get_child_count(), 0)


func test_spawn_screen_scene_opens() -> void:
	var packed: PackedScene = load("res://scenes/levels/screen_spawn.tscn")
	var screen: Node2D = packed.instantiate()
	add_child_autofree(screen)
	await get_tree().process_frame
	assert_eq(screen.get_node("Sky").get_class(), "TileMapLayer")
	assert_eq(screen.get_node("CollisionLayer").get_class(), "TileMapLayer")
	assert_gt((screen.get_node("Sky") as TileMapLayer).get_used_cells().size(), 0)
