extends CharacterBody2D

enum State { IDLE, RUN, JUMP, JUMP_KICK, KICK, CLIMB, CROUCH, PUNCH, DEAD }

# Tuned to Saboteur II feel, still using CharacterBody2D physics.
# Original logic is ~5.5 ticks/s and 1 tile/tick; our tiles are 16px.
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

const BODY_STAND_SIZE := Vector2(14, 42)
const BODY_STAND_POS := Vector2(24, 35)
const BODY_CROUCH_SIZE := Vector2(14, 24)
const BODY_CROUCH_POS := Vector2(24, 44)

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var body_collision: CollisionShape2D = $CollisionShape2D
@onready var punch_area: Area2D = $PunchArea
@onready var ladder_detector: Area2D = $LadderDetector

var current_state: State = State.IDLE
var facing: int = 1
var punch_timer: float = 0.0
var on_ladder: bool = false
var can_climb: bool = false
var is_dead: bool = false
var _kick_left_ground: bool = false
var energy: int = 100
var _iframe: float = 0.0
var _time_since_hit: float = 10.0
var _regen_accum: float = 0.0


func _ready() -> void:
	punch_area.monitoring = false
	energy = max_energy
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

	can_climb = ladder_detector.get_overlapping_areas().size() > 0
	on_ladder = can_climb and abs(Input.get_axis("move_up", "move_down")) > 0.0

	_tick_attack(delta)
	_handle_attack_input()

	if on_ladder:
		_process_climb(delta)
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

	_update_animation()
	move_and_slide()
	_try_unstuck()


func _tick_attack(delta: float) -> void:
	if current_state != State.PUNCH and current_state != State.KICK and current_state != State.JUMP_KICK:
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
	if current_state == State.PUNCH or current_state == State.KICK or current_state == State.JUMP_KICK:
		return

	var moving := absf(Input.get_axis("move_left", "move_right")) > 0.0
	var punch_pressed := Input.is_action_pressed("punch")
	var punch_tap := Input.is_action_just_pressed("punch")
	var jump_tap := Input.is_action_just_pressed("jump")
	var up_held := Input.is_action_pressed("move_up")
	var up_tap := Input.is_action_just_pressed("move_up")

	if is_on_floor():
		var stand_kick := (not can_climb) and (
			(punch_tap and up_held)
			or (up_tap and punch_pressed)
			or (up_tap and not moving)
			or (jump_tap and punch_pressed and not moving)
		)
		if stand_kick:
			_start_stand_kick()
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
	if Input.is_action_pressed("move_down"):
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


func _try_unstuck() -> void:
	if not is_on_floor() or current_state == State.PUNCH or current_state == State.KICK or current_state == State.JUMP_KICK or current_state == State.CROUCH or on_ladder:
		return
	var direction := Input.get_axis("move_left", "move_right")
	if direction == 0.0 or absf(velocity.x) > 8.0:
		return
	var escape := Vector2(direction * 6.0, -10.0)
	if not test_move(global_transform, escape):
		global_position += escape


func _process_climb(_delta: float) -> void:
	velocity.x = 0.0
	velocity.y = Input.get_axis("move_up", "move_down") * climb_speed
	current_state = State.CLIMB


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
			_play_anim(&"climb")
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
