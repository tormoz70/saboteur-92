class_name Player
extends CharacterBody2D

enum State { IDLE, RUN, JUMP, JUMP_KICK, KICK, CLIMB, CROUCH, PUNCH, DEAD }

# Tuned to Saboteur II feel, still using CharacterBody2D physics.
# Original logic is ~5.5 ticks/s and 1 tile/tick; our tiles are 16px.
# Combat/jump chords match the 1987 inlay (see SaboteurControls).
const BODY_STAND_SIZE := Vector2(14, 42)
const BODY_STAND_POS := Vector2(24, 35)
const BODY_CROUCH_SIZE := Vector2(14, 24)
const BODY_CROUCH_POS := Vector2(24, 44)

@export var speed: float = 110.0
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
var _world_mask: int = CollisionLayers.LAYER_WORLD
var _ladder := LadderController.new()
var _lifts := LiftRider.new()

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var body_collision: CollisionShape2D = $CollisionShape2D
@onready var punch_area: Area2D = $PunchArea
@onready var ladder_detector: Area2D = $LadderDetector


func _ready() -> void:
	punch_area.monitoring = false
	energy = max_energy
	floor_snap_length = 16.0
	safe_margin = 0.25
	_world_mask = collision_mask
	_ladder.setup(self)
	_lifts.setup(self)
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

	can_climb = _ladder.overlaps()
	var climb_axis := get_climb_axis()
	_ladder.update_state(climb_axis)
	_lifts.update_state()
	floor_snap_length = 0.0 if on_ladder else 16.0
	collision_mask = 0 if on_ladder else _world_mask

	_tick_attack(delta)
	if not _lifts.is_riding():
		_handle_attack_input()

	if on_ladder:
		_ladder.process_climb(delta, climb_axis)
	elif on_lift and _lifts.process():
		pass
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
	if on_lift and _lifts.is_riding():
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
	if not is_on_floor():
		return

	var direction := TiltSteer.move_axis()
	var moving := absf(direction) > 0.0
	if moving:
		apply_facing(int(sign(direction)))

	match SaboteurControls.resolve_ground(
		moving,
		SaboteurControls.just_up(),
		Input.is_action_just_pressed("punch"),
		can_climb,
		_lifts.can_ride_up()
	):
		SaboteurControls.GroundAction.STAND_KICK:
			_start_stand_kick()
		SaboteurControls.GroundAction.RUNNING_JUMP:
			_start_running_jump(direction)
		SaboteurControls.GroundAction.FLYING_KICK:
			_start_jump_kick()
		SaboteurControls.GroundAction.PUNCH:
			_start_punch()
		_:
			pass


func _process_platformer(delta: float) -> void:
	if not is_on_floor():
		velocity.y += gravity * delta
		if current_state != State.JUMP:
			current_state = State.JUMP
		return

	# Takeoff frame is still on the floor; keep JUMP until vertical speed falls.
	if current_state == State.JUMP:
		if velocity.y < 0.0:
			return
		current_state = State.IDLE

	var direction := TiltSteer.move_axis()
	if SaboteurControls.should_crouch(
		absf(direction) > 0.0,
		SaboteurControls.wants_down(),
		_lifts.can_ride_down()
	):
		velocity.x = 0.0
		current_state = State.CROUCH
	elif direction:
		velocity.x = direction * speed
		apply_facing(int(sign(direction)))
		if current_state != State.PUNCH and current_state != State.KICK:
			current_state = State.RUN
	else:
		velocity.x = move_toward(velocity.x, 0.0, speed)
		current_state = State.IDLE


func is_riding_lift() -> bool:
	return _lifts.is_riding()


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
	var direction := TiltSteer.move_axis()
	if direction == 0.0 or absf(velocity.x) > 8.0:
		return
	var escape := Vector2(direction * 6.0, -10.0)
	if not test_move(global_transform, escape):
		global_position += escape


func get_climb_axis() -> float:
	return SaboteurControls.climb_axis()


func _start_running_jump(direction: float) -> void:
	if direction != 0.0:
		velocity.x = direction * speed
		apply_facing(int(sign(direction)))
	else:
		velocity.x = float(facing) * speed
	velocity.y = jump_velocity
	current_state = State.JUMP
	_ladder.mark_up_spent()


func get_world_mask() -> int:
	return _world_mask


func apply_world_mask() -> void:
	collision_mask = _world_mask


func apply_facing(direction: int) -> void:
	facing = direction
	anim.flip_h = facing < 0


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
	_kick_left_ground = false
	velocity.y = jump_velocity
	velocity.x = float(facing) * speed
	punch_timer = kick_duration
	punch_area.monitoring = true
	punch_area.position = Vector2(24.0 * facing + 16.0, 16.0)


func _update_animation() -> void:
	_set_body_crouch(current_state == State.CROUCH)
	match current_state:
		State.CLIMB:
			_ladder.sync_pose()
			anim.flip_h = false
			if anim.animation != &"climb":
				anim.play(&"climb")
			anim.speed_scale = 0.0
			anim.set_frame_and_progress(_ladder.climb_frame, 0.0)
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


func respawn(to_position: Vector2) -> void:
	is_dead = false
	current_state = State.IDLE
	on_ladder = false
	on_lift = false
	_ladder.reset()
	_lifts.reset()
	can_climb = false
	apply_world_mask()
	_kick_left_ground = false
	_iframe = 0.0
	_time_since_hit = 10.0
	_regen_accum = 0.0
	energy = max_energy
	anim.modulate = Color.WHITE
	global_position = to_position
	velocity = Vector2.ZERO
	EventBus.energy_changed.emit(energy, max_energy)


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		return
	await get_tree().create_timer(0.5).timeout
	respawn(spawn_point)
