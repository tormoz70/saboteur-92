extends CanvasLayer

signal pause_pressed

const ControlChrome := preload("res://scripts/ui/control_chrome.gd")
const MarqueeLabel := preload("res://scripts/ui/marquee_label.gd")

var _chip_fit_pending: bool = false
var _chip_fit_tries: int = 0

@onready var lives_label: Label = $Margin/HBox/VBox/LivesLabel
@onready var score_label: Label = $Margin/HBox/VBox/ScoreLabel
@onready var inventory_label: Label = $Margin/HBox/VBox/InventoryLabel
@onready var energy_dial: Control = $Margin/HBox/EnergyDial
@onready var status_label: MarqueeLabel = $Margin/HBox/VBox/StatusLabel
@onready var bomb_timer_label: Label = $Margin/HBox/VBox/BombTimerLabel
@onready var pause_button: Button = $PauseButton
@onready var chip: PanelContainer = $Margin


func _ready() -> void:
	EventBus.score_changed.connect(_on_score_changed)
	EventBus.item_collected.connect(_on_item_collected)
	EventBus.bomb_planted.connect(_on_bomb_planted)
	EventBus.mission_complete.connect(_on_mission_complete)
	EventBus.player_died.connect(_on_player_died)
	EventBus.energy_changed.connect(_on_energy_changed)
	EventBus.marker_seen.connect(_on_marker_seen)
	pause_button.pressed.connect(pause_pressed.emit)
	ControlChrome.apply(pause_button)
	_refresh()
	_set_status("Find the lab. Start the dump. Leave before it falls.")


func _process(_delta: float) -> void:
	# Fuse ticks in GameManager._process; the label has to follow it.
	# Inventory is signal-driven (item_collected / bomb_planted / _refresh).
	var next_timer := ""
	if GameManager.bomb_planted and GameManager.state == GameManager.GameState.PLAYING:
		next_timer = "Dump: %ds" % ceili(GameManager.bomb_timer)
	if bomb_timer_label.text != next_timer:
		bomb_timer_label.text = next_timer
		bomb_timer_label.visible = next_timer != ""
		_fit_chip()
	pause_button.visible = GameManager.state == GameManager.GameState.PLAYING


func _refresh() -> void:
	lives_label.text = "Lives: %d" % GameManager.lives
	score_label.text = "Score: %d" % GameManager.score
	_update_inventory()
	_set_status("")
	var player := get_tree().get_first_node_in_group("player")
	if player and "energy" in player:
		_on_energy_changed(player.energy, player.max_energy)


func _update_inventory() -> void:
	var items: Array[String] = []
	if GameManager.has_key:
		items.append("Key")
	if GameManager.has_document:
		items.append("Orders")
	if GameManager.has_bomb:
		items.append("Card")
	inventory_label.text = "Items: " + (", ".join(items) if items.size() else "-")
	_fit_chip()


func _on_score_changed(new_score: int) -> void:
	score_label.text = "Score: %d" % new_score


func _on_energy_changed(current: int, max_energy: int) -> void:
	if energy_dial and energy_dial.has_method("set_energy"):
		energy_dial.set_energy(current, max_energy)


func _on_item_collected(_item_type: String) -> void:
	_update_inventory()


func _on_bomb_planted() -> void:
	_set_status("Dump started! Escape!")
	_update_inventory()


func _on_marker_seen(label: String) -> void:
	_set_status("Mark: %s" % label)


func _on_mission_complete() -> void:
	_set_status("")


func _on_player_died() -> void:
	# Inventory is already reset in lose_mission(); refresh it immediately
	# instead of waiting a second for _refresh() (no per-frame rebuild).
	_update_inventory()
	if GameManager.state == GameManager.GameState.LOST:
		_set_status("")
		_refresh()
	else:
		_set_status("You died!")
		await get_tree().create_timer(1.0, false).timeout
		_set_status("")
		_refresh()


func _set_status(text: String) -> void:
	status_label.text = text
	_fit_chip()


func _fit_chip() -> void:
	if chip == null or _chip_fit_pending:
		return
	_chip_fit_pending = true
	_apply_chip_size.call_deferred()


func _apply_chip_size() -> void:
	_chip_fit_pending = false
	if chip == null:
		return
	var min_size := chip.get_combined_minimum_size()
	# Autowrap reports a huge height until the label has a real width.
	if min_size.y > 320.0 and _chip_fit_tries < 5:
		_chip_fit_tries += 1
		_fit_chip()
		return
	_chip_fit_tries = 0
	chip.size = min_size
