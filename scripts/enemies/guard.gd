extends CharacterBody2D

enum AiState { PATROL, CHASE, ATTACK, DEAD }

const ALARM_CHASE_SEC := 0.45

@export var patrol_speed: float = 60.0
@export var chase_speed: float = 110.0
@export var attack_range: float = 45.0
@export var max_health: int = 2
@export var patrol_distance: float = 120.0
@export var attack_damage: int = 12

var health: int
var ai_state: AiState = AiState.PATROL
var patrol_origin: float
var patrol_dir: int = 1
var target: Node2D = null
var attack_cooldown: float = 0.0
var _chase_time: float = 0.0

@onready var anim: AnimatedSprite2D = $AnimatedSprite2D
@onready var sight: Area2D = $SightArea


func _ready() -> void:
	health = max_health
	patrol_origin = global_position.x
	add_to_group("enemies")


func _physics_process(delta: float) -> void:
	if ai_state == AiState.DEAD:
		return

	attack_cooldown = maxf(attack_cooldown - delta, 0.0)
	_detect_player()
	if ai_state == AiState.CHASE:
		_chase_time += delta
		if _chase_time >= ALARM_CHASE_SEC:
			GameManager.raise_alarm()
	else:
		_chase_time = 0.0

	match ai_state:
		AiState.PATROL:
			_patrol(delta)
		AiState.CHASE:
			_chase(delta)
		AiState.ATTACK:
			_attack(delta)

	if not is_on_floor():
		velocity.y += 600.0 * delta

	move_and_slide()
	_update_anim()


func _detect_player() -> void:
	var players := sight.get_overlapping_bodies()
	target = null
	for body in players:
		if body.is_in_group("player"):
			target = body
			break

	if target:
		var dist := global_position.distance_to(target.global_position)
		if dist <= attack_range:
			ai_state = AiState.ATTACK
		else:
			ai_state = AiState.CHASE
	elif ai_state != AiState.PATROL:
		ai_state = AiState.PATROL


func _patrol(_delta: float) -> void:
	var left_bound := patrol_origin - patrol_distance
	var right_bound := patrol_origin + patrol_distance
	velocity.x = patrol_dir * patrol_speed
	if global_position.x <= left_bound:
		patrol_dir = 1
	elif global_position.x >= right_bound:
		patrol_dir = -1
	anim.flip_h = patrol_dir < 0


func _chase(_delta: float) -> void:
	if target == null:
		ai_state = AiState.PATROL
		return
	var dir := signf(target.global_position.x - global_position.x)
	velocity.x = dir * chase_speed
	anim.flip_h = dir < 0


func _attack(_delta: float) -> void:
	velocity.x = 0.0
	if attack_cooldown <= 0.0 and target:
		attack_cooldown = 1.0
		if global_position.distance_to(target.global_position) <= attack_range + 10.0:
			if target.has_method("take_damage"):
				target.take_damage(attack_damage)


func take_damage(amount: int = 1) -> void:
	if ai_state == AiState.DEAD:
		return
	health -= amount
	if health <= 0:
		_die()
	else:
		modulate = Color(1.5, 0.5, 0.5)
		await get_tree().create_timer(0.1).timeout
		modulate = Color.WHITE


func _die() -> void:
	ai_state = AiState.DEAD
	velocity = Vector2.ZERO
	collision_layer = 0
	collision_mask = 0
	EventBus.enemy_killed.emit(self)
	anim.modulate = Color(0.4, 0.4, 0.4)
	await get_tree().create_timer(0.4).timeout
	queue_free()


func _update_anim() -> void:
	if ai_state == AiState.DEAD:
		return
	if ai_state == AiState.ATTACK:
		anim.play("punch")
	elif absf(velocity.x) > 5.0:
		anim.play("run")
	else:
		anim.play("idle")
