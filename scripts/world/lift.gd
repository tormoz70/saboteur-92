class_name Lift
extends AnimatableBody2D

# Original: one character row per tick (~5.5 Hz). World scale is 2× mosaic.
const STEP_PX := 16.0
const SPEED := 88.0

var top_y: float = 0.0
var bottom_y: float = 0.0
var dir: int = 0
var rider: CharacterBody2D = null
var requires_lift_code: bool = false

var _step_acc: float = 0.0
var _width: float = 96.0
var _y: float = 0.0


func setup(world_top: float, world_bottom: float, width: float) -> void:
	top_y = world_top
	bottom_y = world_bottom
	_width = width
	add_to_group("lifts")
	collision_layer = CollisionLayers.LAYER_WORLD
	collision_mask = 0
	sync_to_physics = true


func center_x() -> float:
	return global_position.x + _width * 0.5


func is_centered(player: Node2D) -> bool:
	# Player sprite origin is top-left; stand collider sits 24px in at scale 2.
	var pcx: float = player.global_position.x + 48.0
	return absf(pcx - center_x()) <= 24.0


func carries(player: Node2D, body: CollisionShape2D) -> bool:
	# At a stop the cabin top is flush with the shaft floor tile, so the floor
	# may be the only reported contact while Nina stands on both.
	var rect := body.shape as RectangleShape2D
	if rect == null or not is_centered(player):
		return false
	var feet := body.global_position.y + rect.size.y * 0.5 * body.global_scale.y
	return absf(feet - cabin_y()) <= 2.0


func cabin_y() -> float:
	# sync_to_physics reverts global_position to the last physics transform
	# until the next step, so reading it back right after a move is stale.
	return _y if dir != 0 else global_position.y


func at_top() -> bool:
	return cabin_y() <= top_y + 0.5


func at_bottom() -> bool:
	return cabin_y() >= bottom_y - 0.5


func start_ride(player: CharacterBody2D, want_dir: int) -> bool:
	if requires_lift_code and not GameManager.has_lift_code:
		return false
	if want_dir == 0 or dir != 0:
		return false
	if not is_centered(player):
		return false
	if want_dir < 0 and at_top():
		return false
	if want_dir > 0 and at_bottom():
		return false
	_y = global_position.y
	dir = want_dir
	rider = player
	_step_acc = 0.0
	return true


func stop_ride() -> void:
	dir = 0
	rider = null
	_step_acc = 0.0


func _physics_process(delta: float) -> void:
	if dir == 0:
		return
	if rider != null and is_instance_valid(rider):
		var reverse := 0
		if SaboteurControls.wants_up():
			reverse = -1
		elif SaboteurControls.wants_down():
			reverse = 1
		if reverse != 0 and reverse != dir:
			dir = reverse
	_step_acc += delta
	var step_time := STEP_PX / SPEED
	while _step_acc >= step_time and dir != 0:
		_step_acc -= step_time
		_take_step()


func _take_step() -> void:
	var dest := _y + float(dir) * STEP_PX
	if dir < 0:
		dest = maxf(dest, top_y)
	else:
		dest = minf(dest, bottom_y)
	var moved := dest - _y
	_y = dest
	global_position.y = dest
	if rider != null and is_instance_valid(rider):
		rider.global_position.y += moved
		rider.velocity = Vector2.ZERO
	if absf(moved) < 0.5 or at_top() or at_bottom():
		dir = 0
		rider = null
		_step_acc = 0.0
