extends CanvasLayer
## Pause overlay. Runs while the tree is paused (process_mode ALWAYS), so it
## also routes Esc / Android back for the settings screen opened from it.
##
## Pausing the tree stops GameManager (mission clock, fuse), AudioManager's
## fuse tick, guards, lifts and Nina; SceneTreeTimers that must stop with it
## are created with process_always = false.

signal paused_changed(is_paused: bool)
signal settings_requested
signal main_menu_requested

## Set once the level has streamed in; nothing to pause before that.
var game_ready: bool = false
## Off for headless and demo runs: demos play unattended in a window too, and
## the tilt probe never sets GameManager.demo_mode.
var autopause_enabled: bool = (
	DisplayServer.get_name() != "headless"
	and not TitleScreen.wants_demo(OS.get_cmdline_user_args())
)
var is_paused: bool = false
var settings_menu: CanvasLayer

@onready var panel: Control = %Panel
@onready var info_label: Label = %InfoLabel
@onready var resume_button: Button = %ResumeButton
@onready var settings_button: Button = %SettingsButton
@onready var main_menu_button: Button = %MainMenuButton


func _ready() -> void:
	visible = false
	resume_button.pressed.connect(resume_game)
	settings_button.pressed.connect(_on_settings_pressed)
	main_menu_button.pressed.connect(main_menu_requested.emit)


func can_pause() -> bool:
	return (
		game_ready
		and not GameManager.demo_mode
		and GameManager.state == GameManager.GameState.PLAYING
	)


func pause_game() -> void:
	if is_paused or not can_pause():
		return
	is_paused = true
	get_tree().paused = true
	AudioManager.set_paused(true)
	info_label.text = "TIME %s   SCORE %d" % [
		MissionRecords.format_time(GameManager.mission_time),
		GameManager.score,
	]
	visible = true
	show_menu()
	paused_changed.emit(true)


func resume_game() -> void:
	if not is_paused:
		return
	if settings_menu and settings_menu.is_open():
		settings_menu.close()
	is_paused = false
	visible = false
	get_tree().paused = false
	AudioManager.set_paused(false)
	paused_changed.emit(false)


func show_menu() -> void:
	panel.visible = true
	resume_button.grab_focus()


func return_from_settings() -> void:
	panel.visible = true
	settings_button.grab_focus()


## Esc and Android back: close settings first, otherwise toggle the pause.
func handle_back() -> void:
	if settings_menu and settings_menu.is_open():
		settings_menu.close()
	elif is_paused:
		resume_game()
	else:
		pause_game()


func _unhandled_input(event: InputEvent) -> void:
	if event.is_action_pressed("ui_cancel"):
		handle_back()
		get_viewport().set_input_as_handled()


func _notification(what: int) -> void:
	match what:
		NOTIFICATION_APPLICATION_PAUSED, NOTIFICATION_APPLICATION_FOCUS_OUT:
			if autopause_enabled:
				pause_game()
		NOTIFICATION_WM_GO_BACK_REQUEST:
			if is_node_ready():
				handle_back()


func _on_settings_pressed() -> void:
	panel.visible = false
	settings_requested.emit()
