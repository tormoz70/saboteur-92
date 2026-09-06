extends SceneTree
## Walk right from spawn and confirm Nina stays on the floor (JSON collision).

var _frames := 0
var _player: CharacterBody2D
var _start_y := 0.0
var _min_y := 0.0
var _max_y := 0.0
var _start_x := 0.0


func _initialize() -> void:
	change_scene_to_file("res://scenes/main.tscn")


func _process(_dt: float) -> bool:
	_frames += 1
	if _frames == 20:
		var main := root.get_child(root.get_child_count() - 1)
		var level := main.get_node_or_null("Level01")
		_player = level.get_node_or_null("Player") as CharacterBody2D
		if _player == null:
			push_error("walk_smoke: no player")
			quit()
			return false
		_start_x = _player.global_position.x
		_start_y = _player.global_position.y
		_min_y = _start_y
		_max_y = _start_y
		Input.action_press("move_right")
		print("walk_smoke: start (%.1f, %.1f)" % [_start_x, _start_y])
		return false
	if _player == null:
		if _frames > 180:
			push_error("walk_smoke: player never appeared")
			quit()
		return false
	_min_y = minf(_min_y, _player.global_position.y)
	_max_y = maxf(_max_y, _player.global_position.y)
	if _frames == 140:
		Input.action_release("move_right")
		var dx := _player.global_position.x - _start_x
		var dy := _player.global_position.y - _start_y
		print(
			"walk_smoke: end (%.1f, %.1f) dx=%.1f dy=%.1f y_range=[%.1f, %.1f]"
			% [_player.global_position.x, _player.global_position.y, dx, dy, _min_y, _max_y]
		)
		if dx < 80.0:
			push_error("walk_smoke: did not move right (dx=%.1f)" % dx)
		if dy > 48.0 or _max_y > _start_y + 64.0:
			push_error("walk_smoke: fell through the floor (dy=%.1f)" % dy)
		else:
			print("walk_smoke: OK still on floor")
		quit()
	return false
