extends CanvasLayer

@onready var lives_label: Label = $Margin/HBox/VBox/LivesLabel
@onready var score_label: Label = $Margin/HBox/VBox/ScoreLabel
@onready var inventory_label: Label = $Margin/HBox/VBox/InventoryLabel
@onready var energy_dial: Control = $Margin/HBox/EnergyDial
@onready var status_label: Label = $Margin/HBox/VBox/StatusLabel
@onready var bomb_timer_label: Label = $Margin/HBox/VBox/BombTimerLabel
@onready var result_overlay: Control = $ResultOverlay
@onready var result_title: Label = $ResultOverlay/Panel/Title
@onready var restart_button: Button = $ResultOverlay/Panel/RestartButton


func _ready() -> void:
	EventBus.score_changed.connect(_on_score_changed)
	EventBus.item_collected.connect(_on_item_collected)
	EventBus.bomb_planted.connect(_on_bomb_planted)
	EventBus.mission_complete.connect(_on_mission_complete)
	EventBus.player_died.connect(_on_player_died)
	EventBus.energy_changed.connect(_on_energy_changed)
	restart_button.pressed.connect(_on_restart_pressed)
	_refresh()


func _unhandled_input(event: InputEvent) -> void:
	if not result_overlay.visible:
		return
	if event.is_action_pressed("ui_accept"):
		_on_restart_pressed()
		var vp := get_viewport()
		if vp:
			vp.set_input_as_handled()


func _process(_delta: float) -> void:
	_update_inventory()
	if GameManager.bomb_planted and GameManager.state == GameManager.GameState.PLAYING:
		bomb_timer_label.text = "Bomb: %ds" % ceili(GameManager.bomb_timer)
	else:
		bomb_timer_label.text = ""


func _refresh() -> void:
	lives_label.text = "Lives: %d" % GameManager.lives
	score_label.text = "Score: %d" % GameManager.score
	_update_inventory()
	status_label.text = ""
	var player := get_tree().get_first_node_in_group("player")
	if player and "energy" in player:
		_on_energy_changed(player.energy, player.max_energy)


func _update_inventory() -> void:
	var items: Array[String] = []
	if GameManager.has_key:
		items.append("Key")
	if GameManager.has_document:
		items.append("Doc")
	if GameManager.has_bomb:
		items.append("Bomb")
	inventory_label.text = "Items: " + (", ".join(items) if items.size() else "-")


func _on_score_changed(new_score: int) -> void:
	score_label.text = "Score: %d" % new_score


func _on_energy_changed(current: int, max_energy: int) -> void:
	if energy_dial and energy_dial.has_method("set_energy"):
		energy_dial.set_energy(current, max_energy)


func _on_item_collected(_item_type: String) -> void:
	_update_inventory()


func _on_bomb_planted() -> void:
	status_label.text = "Bomb planted! Escape!"


func _on_mission_complete() -> void:
	status_label.text = ""
	_show_result("Mission complete!", "Play again")


func _on_player_died() -> void:
	if GameManager.state == GameManager.GameState.LOST:
		status_label.text = ""
		_refresh()
		var title := GameManager.fail_reason
		if title.is_empty():
			title = "Game Over"
		_show_result(title, "Restart")
	else:
		status_label.text = "You died!"
		await get_tree().create_timer(1.0).timeout
		status_label.text = ""
		_refresh()


func _show_result(title: String, button_text: String) -> void:
	result_title.text = title
	restart_button.text = button_text
	result_overlay.visible = true
	restart_button.grab_focus()


func _on_restart_pressed() -> void:
	if not result_overlay.visible:
		return
	result_overlay.visible = false
	GameManager.restart_mission()
