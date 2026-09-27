class_name TitleScreen
extends Control
## Title screen, the project's main scene. Demo flags skip it and load the
## level straight away so CI and debug runs behave as before.

const GAME_SCENE := "res://scenes/game.tscn"
const DEMO_ARGS: Array[String] = [
	"--demo",
	"--demo-fuse",
	"--demo-tilt",
	"--demo-maze",
	"--demo-explore",
]

@onready var play_button: Button = %PlayButton
@onready var settings_button: Button = %SettingsButton
@onready var best_label: Label = %BestLabel
@onready var menu: Control = %Menu
@onready var settings_menu: CanvasLayer = $SettingsMenu


func _ready() -> void:
	if wants_demo(OS.get_cmdline_user_args()):
		start_game.call_deferred()
		return
	get_tree().paused = false
	AudioManager.set_paused(false)
	play_button.pressed.connect(start_game)
	settings_button.pressed.connect(open_settings)
	settings_menu.closed.connect(_on_settings_closed)
	_show_best()
	AudioManager.play_music(false)
	play_button.grab_focus()


static func wants_demo(args: PackedStringArray) -> bool:
	for arg in args:
		if arg in DEMO_ARGS:
			return true
	return false


func start_game() -> void:
	GameManager.reset_run_state()
	get_tree().change_scene_to_file(GAME_SCENE)


func open_settings() -> void:
	menu.visible = false
	settings_menu.open()


func _on_settings_closed() -> void:
	menu.visible = true
	settings_button.grab_focus()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel") and settings_menu.is_open():
		settings_menu.close()
		get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	if what != NOTIFICATION_WM_GO_BACK_REQUEST or not is_node_ready():
		return
	if settings_menu.is_open():
		settings_menu.close()
	else:
		get_tree().quit()


func _show_best() -> void:
	var best := MissionRecords.load_best()
	if int(best["wins"]) <= 0:
		best_label.text = "FIND THE LAB. START THE DUMP. GET OUT."
		return
	best_label.text = "BEST TIME %s   BEST SCORE %d" % [
		MissionRecords.format_time(float(best["time"])),
		int(best["score"]),
	]
