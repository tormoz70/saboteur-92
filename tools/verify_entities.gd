extends SceneTree
## Print spawned mission entities and confirm they are active.
## Counts and spawn come from s2_entities.json so a layout change does not rot this.

const ENTITIES_PATH := "res://assets/world/s2_entities.json"

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
	var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(ENTITIES_PATH))
	if typeof(parsed) != TYPE_DICTIONARY:
		push_error("verify_entities: cannot parse %s" % ENTITIES_PATH)
		quit(1)
		return false
	var data: Dictionary = parsed
	var scale := float(data.get("scale", 2))
	var collision: Variant = JSON.parse_string(
		FileAccess.get_file_as_string("res://assets/world/s2_collision.json")
	)
	if typeof(collision) == TYPE_DICTIONARY:
		scale = float(collision.get("scale", scale))
	var player: CharacterBody2D = level.get_node_or_null("Player")
	var items := level.get_node_or_null("Items")
	var guards := level.get_node_or_null("Guards")
	var sabotage := level.get_node_or_null("SabotageTarget")
	var exit_zone := level.get_node_or_null("ExitZone")
	if player == null or items == null or guards == null or sabotage == null or exit_zone == null:
		push_error("verify_entities: missing mission nodes")
		quit(1)
		return false
	var sp: Array = data["spawn"]
	var expect_spawn := Vector2(float(sp[0]), float(sp[1])) * scale
	print("verify_entities: spawn=(%.0f, %.0f)" % [player.global_position.x, player.global_position.y])
	if player.global_position.distance_to(expect_spawn) > 2.0:
		push_error("verify_entities: spawn mismatch")
		quit(1)
		return false
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
	var gi := 0
	var guard_specs: Array = data.get("guards", [])
	for child in guards.get_children():
		var origin: float = child.get("patrol_origin")
		print(
			"verify_entities: guard %s pos=(%.0f, %.0f) origin=%.0f patrol=%.0f"
			% [child.name, child.global_position.x, child.global_position.y, origin, child.get("patrol_distance")]
		)
		if gi < guard_specs.size():
			var want := float(guard_specs[gi]["x"]) * scale
			if absf(origin - want) > 2.0:
				push_error("verify_entities: patrol_origin not at spawn for %s" % child.name)
				quit(1)
				return false
		gi += 1
	if not items.visible or items.process_mode == Node.PROCESS_MODE_DISABLED:
		push_error("verify_entities: Items still hidden/disabled")
		quit(1)
		return false
	var want_items: int = data.get("items", []).size()
	var want_guards: int = guard_specs.size()
	if items.get_child_count() != want_items or guards.get_child_count() != want_guards:
		push_error("verify_entities: unexpected entity counts")
		quit(1)
		return false
	print("verify_entities: OK")
	quit(0)
	return false
