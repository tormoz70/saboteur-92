extends CanvasLayer
## Win / game-over screen: run time, alarm, score and the saved best.
## Demo runs never write records.

signal shown
signal retry_requested
signal main_menu_requested

const WIN_COLOR := Color(0.0, 1.0, 0.0)
const LOSS_COLOR := Color(1.0, 0.0, 0.0)
const BLINK_SEC := 0.4

var records_path: String = MissionRecords.RECORDS_PATH
var last_best: Dictionary = {}

var _blink: float = 0.0

@onready var title_label: Label = %TitleLabel
@onready var time_value: Label = %TimeValue
@onready var alarm_value: Label = %AlarmValue
@onready var score_value: Label = %ScoreValue
@onready var best_time_value: Label = %BestTimeValue
@onready var best_score_value: Label = %BestScoreValue
@onready var record_label: Label = %RecordLabel
@onready var retry_button: Button = %RetryButton
@onready var main_menu_button: Button = %MainMenuButton


func _ready() -> void:
	visible = false
	EventBus.mission_complete.connect(_on_mission_complete)
	EventBus.player_died.connect(_on_player_died)
	retry_button.pressed.connect(retry_requested.emit)
	main_menu_button.pressed.connect(main_menu_requested.emit)


func _process(delta: float) -> void:
	if not visible or record_label.text.is_empty():
		return
	_blink += delta
	# Alpha, not visibility: a hidden label would collapse and shift the panel.
	record_label.modulate.a = 1.0 if fmod(_blink, BLINK_SEC * 2.0) < BLINK_SEC else 0.0


func show_win() -> void:
	var best: Dictionary
	if GameManager.demo_mode:
		best = MissionRecords.load_best(records_path)
		best["new_time"] = false
		best["new_score"] = false
	else:
		best = MissionRecords.submit(
			GameManager.mission_time, GameManager.score, GameManager.alarmed, records_path
		)
	var record := ""
	if best["new_time"] and best["new_score"]:
		record = "NEW BEST TIME AND SCORE!"
	elif best["new_time"]:
		record = "NEW BEST TIME!"
	elif best["new_score"]:
		record = "NEW BEST SCORE!"
	_show("MISSION COMPLETE", WIN_COLOR, best, record)


func show_loss() -> void:
	var reason := GameManager.fail_reason
	if reason.is_empty():
		reason = "Game Over"
	_show(reason.to_upper(), LOSS_COLOR, MissionRecords.load_best(records_path), "")


func _show(title: String, color: Color, best: Dictionary, record: String) -> void:
	last_best = best
	title_label.text = title
	title_label.add_theme_color_override("font_color", color)
	time_value.text = MissionRecords.format_time(GameManager.mission_time)
	alarm_value.text = "RAISED" if GameManager.alarmed else "NOT RAISED"
	alarm_value.add_theme_color_override(
		"font_color", LOSS_COLOR if GameManager.alarmed else WIN_COLOR
	)
	score_value.text = str(GameManager.score)
	best_time_value.text = MissionRecords.format_time(float(best["time"]))
	best_score_value.text = str(int(best["score"])) if int(best["wins"]) > 0 else "-"
	record_label.text = record
	record_label.modulate.a = 1.0
	_blink = 0.0
	visible = true
	retry_button.grab_focus()
	shown.emit()


func _on_mission_complete() -> void:
	show_win()


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		show_loss()
