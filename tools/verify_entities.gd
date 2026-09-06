extends SceneTree
## Print spawned mission entities and confirm they are active.

var _frames := 0


func _initialize() -> void:
	change_scene_to_file("res://scenes/main.tscn")


func _process(_dt: float) -> bool:
	_frames += 1
	if _frames < 20:
		return false
	var main := root.get_child(root.get_child_count() - 1)
	var level := main.get_node_or_null("Level01")
	if level == null:
		push_error("verify_entities: Level01 missing")
		quit(1)
		return false
	var player: CharacterBody2D = level.get_node_or_null("Player")
	var items := level.get_node_or_null("Items")
	var guards := level.get_node_or_null("Guards")
	var sabotage := level.get_node_or_null("SabotageTarget")
	var exit_zone := level.get_node_or_null("ExitZone")
	if player == null or items == null or guards == null or sabotage == null or exit_zone == null:
		push_error("verify_entities: missing mission nodes")
		quit(1)
		return false
	print("verify_entities: spawn=(%.0f, %.0f)" % [player.global_position.x, player.global_position.y])
	for child in items.get_children():
		print(
			"verify_entities: item %s type=%s pos=(%.0f, %.0f) visible=%s process=%d"
			% [
				child.name,
				child.get("item_type"),
				child.global_position.x,
				child.global_position.y,
				child.visible,
				child.process_mode,
			]
		)
	print(
		"verify_entities: sabotage pos=(%.0f, %.0f) visible=%s process=%d"
		% [sabotage.global_position.x, sabotage.global_position.y, sabotage.visible, sabotage.process_mode]
	)
	print(
		"verify_entities: exit pos=(%.0f, %.0f) visible=%s process=%d"
		% [exit_zone.global_position.x, exit_zone.global_position.y, exit_zone.visible, exit_zone.process_mode]
	)
	print("verify_entities: guards=%d" % guards.get_child_count())
	for child in guards.get_children():
		print(
			"verify_entities: guard %s pos=(%.0f, %.0f) patrol=%.0f"
			% [child.name, child.global_position.x, child.global_position.y, child.get("patrol_distance")]
		)
	if not items.visible or items.process_mode == Node.PROCESS_MODE_DISABLED:
		push_error("verify_entities: Items still hidden/disabled")
		quit(1)
		return false
	if items.get_child_count() != 3 or guards.get_child_count() != 3:
		push_error("verify_entities: unexpected entity counts")
		quit(1)
		return false
	print("verify_entities: OK")
	quit(0)
	return false
