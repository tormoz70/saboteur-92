extends Node
## Game scene: the level plus HUD, touch pad, pause, settings and results.
## GameManager.restart_mission() reloads this scene, so "Play again" skips
## the title screen.

const TITLE_SCENE := "res://scenes/main.tscn"

@onready var level: LevelBase = $Level01
@onready var hud: CanvasLayer = $HUD
@onready var touch_controls: CanvasLayer = $TouchControls
@onready var result_screen: CanvasLayer = $ResultScreen
@onready var pause_menu: CanvasLayer = $PauseMenu
@onready var settings_menu: CanvasLayer = $SettingsMenu
@onready var loading: CanvasLayer = $Loading


func _ready() -> void:
	AudioManager.set_paused(false)
	AudioManager.play_music(false)
	pause_menu.settings_menu = settings_menu
	hud.pause_pressed.connect(pause_menu.pause_game)
	pause_menu.paused_changed.connect(_on_paused_changed)
	pause_menu.settings_requested.connect(settings_menu.open)
	pause_menu.main_menu_requested.connect(go_to_title)
	settings_menu.closed.connect(pause_menu.return_from_settings)
	result_screen.shown.connect(_hide_touch_controls)
	result_screen.retry_requested.connect(GameManager.restart_mission)
	result_screen.main_menu_requested.connect(go_to_title)
	if level.world_loaded:
		_on_world_ready()
	else:
		level.world_ready.connect(_on_world_ready, CONNECT_ONE_SHOT)


func go_to_title() -> void:
	get_tree().paused = false
	AudioManager.set_paused(false)
	touch_controls.release_all()
	GameManager.reset_run_state()
	get_tree().change_scene_to_file(TITLE_SCENE)


func _on_world_ready() -> void:
	loading.visible = false
	pause_menu.game_ready = true
	GameManager.start_clock()


func _on_paused_changed(is_paused: bool) -> void:
	if is_paused:
		_hide_touch_controls()
	else:
		touch_controls.visible = true


func _hide_touch_controls() -> void:
	touch_controls.release_all()
	touch_controls.visible = false
