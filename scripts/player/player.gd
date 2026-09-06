extends CharacterBody2D

enum State { IDLE, RUN, JUMP, JUMP_KICK, KICK, CLIMB, CROUCH, PUNCH, DEAD }

# Tuned to Saboteur II feel, still using CharacterBody2D physics.
# Original logic is ~5.5 ticks/s and 1 tile/tick; our tiles are 16px.
const BODY_STAND_SIZE := Vector2(14, 42)
const BODY_STAND_POS := Vector2(24, 35)
const BODY_CROUCH_SIZE := Vector2(14, 24)
const BODY_CROUCH_POS := Vector2(24, 44)
const LiftPlatform := preload("res://scripts/world/lift.gd")
# One rung = one mosaic cell (8px) at world scale 2. Pose swaps on that same tick.
const CLIMB_STEP_PX := 16.0

@export var speed: float = 110.0
@export var crouch_speed: float = 40.0
@export var jump_velocity: float = -270.0
@export var gravity: float = 820.0
@export var climb_speed: float = 56.0
@export var punch_duration: float = 0.32
@export var kick_duration: float = 0.42
@export var max_energy: int = 100
@export var iframe_time: float = 0.55
@export var regen_delay: float = 1.25
@export var regen_per_second: float = 20.0
@export var spawn_point: Vector2 = Vector2(48, 184)
@export var max_fall_speed: float = 420.0

var current_state: State = State.IDLE
var facing: int = 1
var punch_timer: float = 0.0
var on_ladder: bool = false
var on_lift: bool = false
var can_climb: bool = false
var is_dead: bool = false
var energy: int = 100
var _kick_left_ground: bool = false
var _iframe: float = 0.0
var _time_since_hit: float = 10.0
var _regen_accum: float = 0.0
var _climb_step_timer: float = 0.0
var _climb_frame: int = 0
var _lift: LiftPlatform = null
var _probe_shape := RectangleShape2D.new()
var _probe_query := PhysicsShapeQueryParameters2D.new()

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var body_collision: CollisionShape2D = $CollisionShape2D
@onready var punch_area: Area2D = $PunchArea
@onready var ladder_detector: Area2D = $LadderDetector


func _ready() -> void:
	punch_area.monitoring = false
	energy = max_energy
	floor_snap_length = 16.0
	safe_margin = 0.25
	EventBus.player_died.connect(_on_player_died)
	EventBus.energy_changed.emit(energy, max_energy)


func _physics_process(delta: float) -> void:
	if is_dead or GameManager.state != GameManager.GameState.PLAYING:
		velocity = Vector2.ZERO
		move_and_slide()
		return

	_iframe = maxf(_iframe - delta, 0.0)
	if _iframe <= 0.0:
		anim.modulate = Color.WHITE
	_time_since_hit += delta
	_tick_regen(delta)

	can_climb = _ladder_overlaps()
	var climb_axis := _climb_axis()
	_update_ladder_state(climb_axis)
	_update_lift_state()
	floor_snap_length = 0.0 if on_ladder else 16.0
	collision_mask = 0 if on_ladder else 4

	_tick_attack(delta)
	if not (on_lift and _lift != null and _lift.dir != 0):
		_handle_attack_input()

	if on_ladder:
		_process_climb(delta, climb_axis)
	elif on_lift:
		_process_lift()
	elif current_state == State.PUNCH or current_state == State.KICK:
		velocity.x = 0.0
		if not is_on_floor():
			velocity.y += gravity * delta
	elif current_state == State.JUMP_KICK:
		if not is_on_floor():
			_kick_left_ground = true
			velocity.y += gravity * delta
		velocity.x = float(facing) * speed
		if _kick_left_ground and is_on_floor():
			punch_area.monitoring = false
			current_state = State.IDLE
	else:
		_process_platformer(delta)

	if not on_ladder:
		velocity.y = minf(velocity.y, max_fall_speed)
	_update_animation()
	if on_lift and _lift != null and _lift.dir != 0:
		return
	move_and_slide()
	_try_unstuck()


func _tick_attack(delta: float) -> void:
	if (
		current_state != State.PUNCH
		and current_state != State.KICK
		and current_state != State.JUMP_KICK
	):
		return
	punch_timer -= delta
	if punch_timer > 0.0:
		return
	punch_area.monitoring = false
	if current_state == State.JUMP_KICK:
		# Keep the yoko-geri pose until landing; only the hitbox turns off.
		return
	if is_on_floor():
		current_state = State.IDLE
	else:
		current_state = State.JUMP


func _handle_attack_input() -> void:
	if on_ladder:
		return
	if current_state == State.PUNCH or current_state == State.KICK or current_state == State.JUMP_KICK:
		return

	var moving := absf(Input.get_axis("move_left", "move_right")) > 0.0
	var punch_pressed := Input.is_action_pressed("punch")
	var punch_tap := Input.is_action_just_pressed("punch")
	var jump_tap := Input.is_action_just_pressed("jump")
	var up_held := Input.is_action_pressed("move_up")
	var up_tap := Input.is_action_just_pressed("move_up")

	if is_on_floor():
		var on_lift_center := on_lift and _lift != null and _lift.is_centered(self)
		var stand_kick := (not can_climb) and (not on_lift_center) and (
			(punch_tap and up_held)
			or (up_tap and punch_pressed)
			or (up_tap and not moving)
			or (jump_tap and punch_pressed and not moving)
		)
		if stand_kick:
			_start_stand_kick()
		elif can_climb and (jump_tap or up_tap):
			pass
		elif jump_tap and punch_pressed:
			velocity.y = jump_velocity
			_start_jump_kick()
		elif punch_tap:
			_start_punch()
		elif jump_tap:
			velocity.y = jump_velocity if moving else jump_velocity * 0.82
			current_state = State.JUMP
	elif punch_tap:
		_start_jump_kick()


func _process_platformer(delta: float) -> void:
	if not is_on_floor():
		velocity.y += gravity * delta
		if current_state != State.JUMP:
			current_state = State.JUMP
		return

	# Still on the floor the takeoff frame; only land when vertical speed has fallen.
	if current_state == State.JUMP and velocity.y >= 0.0:
		current_state = State.IDLE

	var direction := Input.get_axis("move_left", "move_right")
	if Input.is_action_pressed("move_down") and not (
		on_lift and _lift != null and _lift.is_centered(self)
	):
		if direction:
			velocity.x = direction * crouch_speed
			facing = int(sign(direction))
			anim.flip_h = facing < 0
		else:
			velocity.x = move_toward(velocity.x, 0.0, crouch_speed)
		current_state = State.CROUCH
	elif direction:
		velocity.x = direction * speed
		facing = int(sign(direction))
		anim.flip_h = facing < 0
		if current_state != State.PUNCH and current_state != State.KICK:
			current_state = State.RUN
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		current_state = State.IDLE


func _update_lift_state() -> void:
	if on_ladder:
		_leave_lift()
		return
	var found: LiftPlatform = null
	for i in range(get_slide_collision_count()):
		var col := get_slide_collision(i)
		var n := col.get_collider() as LiftPlatform
		if n != null:
			found = n
			break
	if found == null:
		if on_lift and _lift != null and _lift.dir != 0:
			return
		_leave_lift()
		return
	on_lift = true
	_lift = found


func is_riding_lift() -> bool:
	return on_lift and _lift != null and _lift.dir != 0


func _leave_lift() -> void:
	if _lift != null and _lift.rider == self:
		_lift.stop_ride()
	on_lift = false
	_lift = null


func _process_lift() -> void:
	current_state = State.IDLE
	if _lift == null:
		return
	if _lift.dir != 0:
		if Input.is_action_pressed("move_up") and _lift.dir > 0:
			_lift.dir = -1
		elif Input.is_action_pressed("move_down") and _lift.dir < 0:
			_lift.dir = 1
		velocity = Vector2.ZERO
		return
	var want := 0
	if Input.is_action_pressed("move_up"):
		want = -1
	elif Input.is_action_pressed("move_down"):
		want = 1
	if want != 0 and _lift.start_ride(self, want):
		velocity = Vector2.ZERO
		return
	var direction := Input.get_axis("move_left", "move_right")
	if direction:
		velocity.x = direction * speed
		facing = int(sign(direction))
		anim.flip_h = facing < 0
		current_state = State.RUN
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)


func _try_unstuck() -> void:
	if (
		not is_on_floor()
		or current_state == State.PUNCH
		or current_state == State.KICK
		or current_state == State.JUMP_KICK
		or current_state == State.CROUCH
		or on_ladder
		or on_lift
	):
		return
	var direction := Input.get_axis("move_left", "move_right")
	if direction == 0.0 or absf(velocity.x) > 8.0:
		return
	var escape := Vector2(direction * 6.0, -10.0)
	if not test_move(global_transform, escape):
		global_position += escape


func _climb_axis() -> float:
	return Input.get_axis("move_up", "move_down")


func _ladder_overlaps() -> bool:
	var col := ladder_detector.get_child(0) as CollisionShape2D
	if col == null or col.shape == null:
		return false
	return _ladder_query(col.shape, col.global_transform)


func _update_ladder_state(climb_axis: float) -> void:
	var h_axis := Input.get_axis("move_left", "move_right")
	var want_climb := absf(climb_axis) > 0.0
	var running_jump := (
		not on_ladder
		and is_on_floor()
		and absf(h_axis) > 0.0
		and Input.is_action_pressed("move_up")
	)
	if on_ladder:
		if not can_climb:
			_leave_ladder()
			return
		if absf(h_axis) > 0.0 and not want_climb:
			_leave_ladder()
			return
		return
	if running_jump or not can_climb or not want_climb:
		return
	# Hatch: Down only if rungs continue under the floor. Up only if rungs continue above.
	if climb_axis > 0.0 and _ladder_below_feet():
		_enter_ladder()
		_climb_take_step(climb_axis)
	elif climb_axis < 0.0 and _ladder_above_feet():
		_enter_ladder()
		_climb_take_step(climb_axis)


func _enter_ladder() -> void:
	on_ladder = true
	collision_mask = 0
	floor_snap_length = 0.0
	velocity = Vector2.ZERO
	_climb_step_timer = 0.0
	_snap_to_ladder()


func _leave_ladder() -> void:
	on_ladder = false
	collision_mask = 4
	floor_snap_length = 16.0
	velocity = Vector2.ZERO
	_snap_onto_support()


func _snap_to_ladder() -> void:
	var areas := ladder_detector.get_overlapping_areas()
	if areas.is_empty():
		return
	var col := areas[0].get_child(0) as CollisionShape2D
	if col == null:
		return
	global_position.x = col.global_position.x - BODY_STAND_POS.x * scale.x


func _snap_onto_support() -> void:
	var space := get_world_2d().direct_space_state
	var cx := global_position.x + BODY_STAND_POS.x * scale.x
	var from := Vector2(cx, global_position.y + 4.0)
	var q := PhysicsRayQueryParameters2D.create(from, from + Vector2(0.0, 96.0))
	q.collision_mask = 4
	q.exclude = [get_rid()]
	var hit := space.intersect_ray(q)
	if hit.is_empty():
		return
	var n: Vector2 = hit.normal
	if n.y > -0.5:
		return
	var feet_off := (BODY_STAND_POS.y + BODY_STAND_SIZE.y * 0.5) * scale.y
	global_position.y = hit.position.y - feet_off


func _process_climb(delta: float, axis: float) -> void:
	velocity = Vector2.ZERO
	current_state = State.CLIMB
	_snap_to_ladder()
	if absf(axis) < 0.1:
		_climb_step_timer = 0.0
		return
	var step_time := CLIMB_STEP_PX / maxf(climb_speed, 1.0)
	_climb_step_timer += delta
	while _climb_step_timer >= step_time and on_ladder:
		if not _climb_take_step(axis):
			_climb_step_timer = 0.0
			break
		_climb_step_timer -= step_time


func _climb_take_step(axis: float) -> bool:
	var step := Vector2(0.0, signf(axis) * CLIMB_STEP_PX)
	var dest := global_position + step
	if not _ladder_overlaps_at(dest):
		# Ladder ended: stand on a close floor, otherwise hang on the last rung.
		if axis > 0.0:
			_dismount_if_close_floor()
		else:
			_dismount_if_landing()
		return false
	if axis > 0.0:
		var floor_y := _blocking_floor_y(step.y)
		if floor_y < INF:
			_dismount_to_y(floor_y)
			return false
	else:
		var ceil_y := _blocking_ceiling_y(step.y)
		if ceil_y < INF:
			# Climbing up: y decreases. Dismount when feet rise to the lid.
			if _feet_y() + step.y <= ceil_y + 2.0:
				_dismount_to_y(ceil_y)
			else:
				_dismount_if_landing()
			return false
	move_and_collide(step)
	_sync_climb_pose()
	return true


func _sync_climb_pose() -> void:
	# Original flips the same sprite every tile; lock the pose to world Y so
	# up and down stay on the same rungs instead of skipping every other frame.
	_climb_frame = int(floor(global_position.y / CLIMB_STEP_PX)) & 1


func _ladder_overlaps_at(origin: Vector2) -> bool:
	var col := ladder_detector.get_child(0) as CollisionShape2D
	if col == null or col.shape == null:
		return false
	var xf := col.global_transform
	xf.origin += origin - global_position
	return _ladder_query(col.shape, xf)


func _feet_y() -> float:
	return global_position.y + (BODY_STAND_POS.y + BODY_STAND_SIZE.y * 0.5) * scale.y


func _body_cx() -> float:
	return global_position.x + BODY_STAND_POS.x * scale.x


func _ladder_at_world(point: Vector2) -> bool:
	return _ladder_hits(point, Vector2(8.0, 8.0))


func _ladder_above_feet() -> bool:
	return _ladder_probe(Vector2(BODY_STAND_POS.x, 16.0) * scale, Vector2(12.0, 20.0) * scale)


func _ladder_below_feet() -> bool:
	# Entirely under the soles so a dead-end floor with rungs at foot height
	# does not count as a hatch.
	return _ladder_probe(
		Vector2(BODY_STAND_POS.x * scale.x, _feet_y() - global_position.y + 24.0),
		Vector2(10.0, 16.0)
	)


func _ladder_probe(local_center: Vector2, size: Vector2) -> bool:
	return _ladder_hits(global_position + local_center, size)


func _ladder_hits(center: Vector2, size: Vector2) -> bool:
	_probe_shape.size = size
	return _ladder_query(_probe_shape, Transform2D(0.0, center))


func _ladder_query(shape: Shape2D, xf: Transform2D) -> bool:
	# Reused query keeps leftover fields. Set every field the four old
	# functions wrote, every call, or a prior detector/probe leaks in.
	_probe_query.shape = shape
	_probe_query.transform = xf
	_probe_query.collision_mask = ladder_detector.collision_mask
	_probe_query.collide_with_areas = true
	_probe_query.collide_with_bodies = false
	_probe_query.exclude = [get_rid()]
	return get_world_2d().direct_space_state.intersect_shape(_probe_query, 1).size() > 0


func _blocking_floor_y(dy: float) -> float:
	var hit := _vertical_solid(_feet_y() - 1.0, _feet_y() + dy + 2.0)
	if hit.is_empty():
		return INF
	var fy: float = hit.position.y
	# Hatch: rungs continue under the lid, so the floor is walkable but climbable-through.
	if _ladder_at_world(Vector2(_body_cx(), fy + 32.0)):
		return INF
	return fy


func _blocking_ceiling_y(dy: float) -> float:
	var head := global_position.y + 2.0
	var hit := _vertical_solid(head, head + dy - 2.0)
	if hit.is_empty():
		return INF
	var cy: float = hit.position.y
	# Shaft continues through the lid — keep climbing.
	if _ladder_at_world(Vector2(_body_cx(), cy - 32.0)):
		return INF
	# Landing lid (ladder ends here): keep climbing through until feet reach it.
	if _ladder_at_world(Vector2(_body_cx(), cy + 2.0)) and _feet_y() + dy > cy + 2.0:
		return INF
	return cy


func _vertical_solid(from_y: float, to_y: float) -> Dictionary:
	var space := get_world_2d().direct_space_state
	var cx := _body_cx()
	var q := PhysicsRayQueryParameters2D.create(Vector2(cx, from_y), Vector2(cx, to_y))
	q.collision_mask = 4
	q.exclude = [get_rid()]
	return space.intersect_ray(q)


func _dismount_to_y(floor_y: float) -> void:
	var feet_off := (BODY_STAND_POS.y + BODY_STAND_SIZE.y * 0.5) * scale.y
	on_ladder = false
	collision_mask = 4
	floor_snap_length = 16.0
	velocity = Vector2.ZERO
	global_position.y = floor_y - feet_off
	current_state = State.IDLE


func _dismount_if_close_floor() -> void:
	var hit := _vertical_solid(_feet_y() - 2.0, _feet_y() + 24.0)
	if hit.is_empty():
		return
	var n: Vector2 = hit.normal
	if n.y > -0.5:
		return
	_dismount_to_y(hit.position.y)


func _dismount_if_landing() -> bool:
	var space := get_world_2d().direct_space_state
	var feet := _feet_y()
	var cx := _body_cx()
	for side in [-48.0, 48.0, -72.0, 72.0]:
		var from := Vector2(cx + side, feet - 12.0)
		var q := PhysicsRayQueryParameters2D.create(from, from + Vector2(0.0, 28.0))
		q.collision_mask = 4
		q.exclude = [get_rid()]
		var hit := space.intersect_ray(q)
		if hit.is_empty():
			continue
		var n: Vector2 = hit.normal
		if n.y > -0.5:
			continue
		var fy: float = hit.position.y
		if absf(fy - feet) > 20.0:
			continue
		_dismount_to_y(fy)
		return true
	return false


func _start_punch() -> void:
	current_state = State.PUNCH
	punch_timer = punch_duration
	punch_area.monitoring = true
	punch_area.position = Vector2(24.0 * facing + 12.0, 19.0)


func _start_stand_kick() -> void:
	current_state = State.KICK
	punch_timer = kick_duration
	punch_area.monitoring = true
	punch_area.position = Vector2(24.0 * facing + 14.0, 8.0)


func _start_jump_kick() -> void:
	current_state = State.JUMP_KICK
	_kick_left_ground = not is_on_floor()
	punch_timer = kick_duration
	punch_area.monitoring = true
	punch_area.position = Vector2(24.0 * facing + 16.0, 16.0)


func _update_animation() -> void:
	_set_body_crouch(current_state == State.CROUCH)
	match current_state:
		State.CLIMB:
			_sync_climb_pose()
			anim.flip_h = false
			if anim.animation != &"climb":
				anim.play(&"climb")
			anim.speed_scale = 0.0
			anim.set_frame_and_progress(_climb_frame, 0.0)
		State.PUNCH:
			_play_anim(&"punch")
		State.KICK:
			_play_anim(&"kick")
		State.JUMP_KICK:
			_play_anim(&"jump_kick")
		State.JUMP:
			_play_anim(&"jump")
		State.RUN:
			_play_anim(&"run")
		State.CROUCH:
			_play_anim(&"crouch")
		State.DEAD:
			_play_anim(&"death")
		_:
			_play_anim(&"idle")


func _play_anim(anim_name: StringName) -> void:
	anim.speed_scale = 1.0
	if anim.animation != anim_name:
		anim.play(anim_name)


func _set_body_crouch(crouching: bool) -> void:
	var shape := body_collision.shape as RectangleShape2D
	if crouching:
		shape.size = BODY_CROUCH_SIZE
		body_collision.position = BODY_CROUCH_POS
	else:
		shape.size = BODY_STAND_SIZE
		body_collision.position = BODY_STAND_POS


func _tick_regen(delta: float) -> void:
	if on_ladder:
		_regen_accum = 0.0
		return
	if energy >= max_energy:
		_regen_accum = 0.0
		return
	if _time_since_hit < regen_delay:
		_regen_accum = 0.0
		return
	_regen_accum += regen_per_second * delta
	var recovered := int(_regen_accum)
	if recovered <= 0:
		return
	_regen_accum -= float(recovered)
	energy = mini(energy + recovered, max_energy)
	EventBus.energy_changed.emit(energy, max_energy)


func take_damage(amount: int = 12) -> void:
	if is_dead or GameManager.demo_mode or _iframe > 0.0:
		return
	energy = maxi(energy - amount, 0)
	_iframe = iframe_time
	_time_since_hit = 0.0
	_regen_accum = 0.0
	anim.modulate = Color(1.4, 0.45, 0.45)
	EventBus.energy_changed.emit(energy, max_energy)
	if energy > 0:
		return
	is_dead = true
	current_state = State.DEAD
	GameManager.lose_mission()


func respawn(spawn_point: Vector2) -> void:
	is_dead = false
	current_state = State.IDLE
	on_ladder = false
	on_lift = false
	_lift = null
	can_climb = false
	collision_mask = 4
	_kick_left_ground = false
	_iframe = 0.0
	_time_since_hit = 10.0
	_regen_accum = 0.0
	energy = max_energy
	anim.modulate = Color.WHITE
	global_position = spawn_point
	velocity = Vector2.ZERO
	EventBus.energy_changed.emit(energy, max_energy)


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		return
	await get_tree().create_timer(0.5).timeout
	respawn(spawn_point)
