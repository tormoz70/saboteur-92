class_name ChordTouchButton
extends TouchScreenButton
## Presses every action in `chord` while the finger is down.
##
## A hold count is shared across the pad, so sliding from Left onto Jump-Left
## does not drop `move_left` for a frame.

static var _holds: Dictionary = {}

@export var chord: PackedStringArray = []

var _latched := false


func _ready() -> void:
	pressed.connect(_latch)
	released.connect(_unlatch)
	tree_exiting.connect(_unlatch)


func _latch() -> void:
	if _latched:
		return
	_latched = true
	for action in chord:
		retain(StringName(action))


func _unlatch() -> void:
	if not _latched:
		return
	_latched = false
	for action in chord:
		drop(StringName(action))


static func retain(action: StringName) -> void:
	var n := int(_holds.get(action, 0)) + 1
	_holds[action] = n
	if n == 1:
		Input.action_press(action)


static func drop(action: StringName) -> void:
	var n := maxi(int(_holds.get(action, 0)) - 1, 0)
	_holds[action] = n
	if n == 0:
		Input.action_release(action)


static func reset_holds() -> void:
	for action in _holds.keys():
		if int(_holds[action]) > 0 and InputMap.has_action(action):
			Input.action_release(action)
	_holds.clear()
