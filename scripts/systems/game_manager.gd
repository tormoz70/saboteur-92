extends Node

enum GameState { PLAYING, WON, LOST }

var state: GameState = GameState.PLAYING
var lives: int = 3
var score: int = 0
var has_key: bool = false
var has_document: bool = false
var has_bomb: bool = false
var bomb_planted: bool = false
var bomb_timer: float = 0.0
var demo_mode: bool = false

# Escape run after planting, measured on the Stage 2 layout in s2_entities.json.
# Path: sabotage (3480, 832) PNG → exit (1800, 808) PNG along the spawn hall.
# Horizontal 1680 PNG = 3360 world px / 110 px/s ≈ 31 s of sprinting.
# Plus turn-around and ladder-snap slack ≈ 19 s. Standing still for the full
# fuse is a loss; the only win is the green exit.
const BOMB_FUSE_TIME := 50.0


func _ready() -> void:
	get_tree().debug_collisions_hint = false
	get_tree().debug_navigation_hint = false
	get_tree().debug_paths_hint = false
	EventBus.enemy_killed.connect(_on_enemy_killed)
	EventBus.item_collected.connect(_on_item_collected)
	EventBus.bomb_planted.connect(_on_bomb_planted)


func _process(delta: float) -> void:
	if bomb_planted and state == GameState.PLAYING:
		bomb_timer -= delta
		if bomb_timer <= 0.0:
			bomb_timer = 0.0
			# Fuse burnt out: mission failed, not a single life. Items are already
			# gone so a mid-run respawn would be unwinnable.
			lives = 1
			lose_mission()


func reset_inventory() -> void:
	has_key = false
	has_document = false
	has_bomb = false
	bomb_planted = false
	bomb_timer = 0.0


func add_score(points: int) -> void:
	score += points
	EventBus.score_changed.emit(score)


func win_mission() -> void:
	if state != GameState.PLAYING:
		return
	state = GameState.WON
	EventBus.mission_complete.emit()


func restart_mission() -> void:
	# Autoload survives scene reload — reset everything explicitly.
	state = GameState.PLAYING
	lives = 3
	score = 0
	demo_mode = false
	reset_inventory()
	get_tree().reload_current_scene()


func lose_mission() -> void:
	if state != GameState.PLAYING:
		return
	lives -= 1
	if lives <= 0:
		state = GameState.LOST
	else:
		reset_inventory()
	EventBus.player_died.emit()


func _on_enemy_killed(_enemy: Node) -> void:
	add_score(100)


func _on_item_collected(item_type: String) -> void:
	match item_type:
		"key":
			has_key = true
		"document":
			has_document = true
		"bomb":
			has_bomb = true
	add_score(50)


func _on_bomb_planted() -> void:
	if bomb_planted:
		return
	bomb_planted = true
	has_bomb = false
	bomb_timer = BOMB_FUSE_TIME
