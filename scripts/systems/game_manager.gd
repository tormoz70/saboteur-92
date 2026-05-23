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

const BOMB_FUSE_TIME := 10.0


func _ready() -> void:
	get_tree().debug_collisions_hint = false
	get_tree().debug_navigation_hint = false
	get_tree().debug_paths_hint = false
	EventBus.enemy_killed.connect(_on_enemy_killed)
	EventBus.item_collected.connect(_on_item_collected)
	EventBus.bomb_planted.connect(_on_bomb_planted)
	EventBus.player_died.connect(_on_player_died)


func _process(delta: float) -> void:
	if bomb_planted and state == GameState.PLAYING:
		bomb_timer -= delta
		if bomb_timer <= 0.0:
			add_score(500)
			win_mission()


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


func _on_player_died() -> void:
	pass
