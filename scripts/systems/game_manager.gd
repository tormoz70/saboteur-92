extends Node

enum GameState { PLAYING, WON, LOST }

const ESCAPE_BONUS := 500

var state: GameState = GameState.PLAYING
var lives: int = 3
var score: int = 0
var has_key: bool = false
var has_document: bool = false
var has_bomb: bool = false
var bomb_planted: bool = false
var bomb_timer: float = 0.0
var demo_mode: bool = false
var fail_reason: String = ""
# Seconds after planting. s2_entities.json overwrites this so the timer lives
# next to the layout it covers. Default matches the Stage 2 hall: sabotage →
# exit is 3360 world px / 110 px/s ≈ 31 s of sprinting plus turn-around slack.
var bomb_fuse_time: float = 50.0


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
			fail_mission("The bomb exploded")


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
	add_score(ESCAPE_BONUS)
	state = GameState.WON
	EventBus.mission_complete.emit()


func restart_mission() -> void:
	# Autoload survives scene reload — reset everything explicitly.
	state = GameState.PLAYING
	lives = 3
	score = 0
	demo_mode = false
	fail_reason = ""
	reset_inventory()
	get_tree().reload_current_scene()


func fail_mission(reason: String = "Game Over") -> void:
	if state != GameState.PLAYING:
		return
	lives = 0
	state = GameState.LOST
	fail_reason = reason
	EventBus.player_died.emit()


func lose_mission() -> void:
	if state != GameState.PLAYING:
		return
	lives -= 1
	if lives <= 0:
		state = GameState.LOST
		fail_reason = "Game Over"
		EventBus.player_died.emit()
		return
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
	bomb_timer = bomb_fuse_time
