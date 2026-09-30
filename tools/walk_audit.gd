extends SceneTree
## Walks Nina along every red-brick floor and horizontal white beam, both ways.
## The runs also pass every bookcase and step onto the tightropes at the
## crossbars. Fails when a brick/beam top has no collision, when she drops
## below the floor she walks on (a rope counts: it is level with the
## crossbars), or when she stalls against something invisible.
##
## godot --headless --fixed-fps 60 -s tools/walk_audit.gd

const CELL := 8
const HEADROOM := 6
const BRICK := [Vector2i(1, 0), Vector2i(2, 0)]
const BEAM := Vector2i(13, 0)
const MIN_RUN := 4
# Ladder holes and single missing cells Nina must walk across.
const MAX_GAP := 2
const STALL_FRAMES := 20
# Soles may sit this far below the floor top, in cells (a rope sink was 0.5).
const SINK_CELLS := 0.1
# Step-up (20 world px) at the end of a run is allowed.
const RISE_CELLS := 1.3
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]
# Wall-clock seconds; a script error before quit() would otherwise idle forever.
const WATCHDOG_SEC := 900

var _level: Node2D
var _player: CharacterBody2D
var _scale := 2.0
# Player's body x and sole y inside its 48x56 frame. Read from player.gd: a
# -s script cannot name the Player class, it depends on autoloads.
var _body_x := 0.0
var _sole_y := 0.0
var _solid: Dictionary = {}
var _floor: Dictionary = {}
var _problems := 0


func _initialize() -> void:
	_run.call_deferred()


func _process(_delta: float) -> bool:
	if Time.get_ticks_msec() > WATCHDOG_SEC * 1000:
		push_error("walk_audit: gave up after %d s" % WATCHDOG_SEC)
		quit(2)
	return false


func _run() -> void:
	root.get_node("GameManager").set("demo_mode", true)
	_level = (load("res://scenes/levels/level_01.tscn") as PackedScene).instantiate()
	root.add_child(_level)
	while not _level.world_loaded:
		await process_frame
	_player = _level.get_node("Player")
	_scale = _player.scale.x
	var consts := (_player.get_script() as GDScript).get_script_constant_map()
	var body_pos: Vector2 = consts["BODY_STAND_POS"]
	var body_size: Vector2 = consts["BODY_STAND_SIZE"]
	_body_x = body_pos.x
	_sole_y = body_pos.y + body_size.y * 0.5
	for group in ["Guards", "Panthers"]:
		var node := _level.get_node_or_null(group)
		if node:
			node.free()
	_collect()
	var runs := _find_runs()
	var cells := 0
	for r in runs:
		cells += r.z - r.y
	print("walk_audit: %d floor tops, %d runs, %d cells" % [_floor.size(), runs.size(), cells])
	for r in runs:
		await _audit_run(r)
	print("walk_audit: %d problem(s)" % _problems)
	quit(1 if _problems > 0 else 0)


func _collect() -> void:
	for chunk in _level.get_node("WorldMap").get_children():
		var base := Vector2i((chunk as Node2D).position / float(CELL))
		var col := chunk.get_node("CollisionLayer") as TileMapLayer
		for c in col.get_used_cells():
			var kind := TileMapUtils.get_collision_type(col, c)
			if kind == "solid" or kind == "oneway":
				_solid[c + base] = true
		for layer_name in ["Structure", "StructureFront"]:
			var layer := chunk.get_node_or_null(layer_name) as TileMapLayer
			if layer == null:
				continue
			for c in layer.get_used_cells():
				if layer.get_cell_atlas_coords(c) in BRICK:
					_floor[c + base] = true
		for layer_name in ["Interior1", "Interior2"]:
			var layer := chunk.get_node_or_null(layer_name) as TileMapLayer
			if layer == null:
				continue
			for c in layer.get_used_cells():
				var alt := layer.get_cell_alternative_tile(c)
				if (
					layer.get_cell_atlas_coords(c) == BEAM
					and alt & TileSetAtlasSource.TRANSFORM_TRANSPOSE == 0
				):
					_floor[c + base] = true
	# Keep only the top of each brick/beam stack: that is what Nina stands on.
	for c in _floor.keys():
		if _floor.has(c + Vector2i.UP):
			_floor.erase(c)
	for c in _floor.keys():
		if not _solid.has(c):
			_fail("floor tile without collision at cell (%d, %d)" % [c.x, c.y])


func _open_above(x: int, y: int, from: int) -> bool:
	for dy in range(from, HEADROOM + 1):
		if _solid.has(Vector2i(x, y - dy)):
			return false
	return true


func _surface(x: int, y: int) -> bool:
	return _solid.has(Vector2i(x, y)) and _open_above(x, y, 1)


## Vector3i(row, first cell, one past the last cell) of every walkable stretch
## that carries brick or beam tops.
func _find_runs() -> Array[Vector3i]:
	var seen: Dictionary = {}
	var runs: Array[Vector3i] = []
	for c: Vector2i in _floor.keys():
		if seen.has(c) or not _surface(c.x, c.y):
			continue
		var lo := _extend(c, -1)
		var hi := _extend(c, 1)
		var tops := 0
		for x in range(lo, hi + 1):
			var cell := Vector2i(x, c.y)
			if _floor.has(cell):
				seen[cell] = true
				tops += 1
		if hi - lo + 1 >= MIN_RUN and tops >= 2:
			runs.append(Vector3i(c.y, lo, hi + 1))
	runs.sort()
	return runs


func _extend(from: Vector2i, step: int) -> int:
	var last := from.x
	var x := from.x + step
	var gap := 0
	while gap <= MAX_GAP:
		if _surface(x, from.y):
			last = x
			gap = 0
		elif _open_above(x, from.y, 0):
			gap += 1
		else:
			break
		x += step
	return last


func _audit_run(r: Vector3i) -> void:
	var row := float(r.x)
	var a := float(r.y) + 1.0
	var b := float(r.z) - 1.0
	if b - a < 1.0:
		return
	var label := "row %d cells %d..%d" % [r.x, r.y, r.z]
	if await _place(a, row):
		await _walk(b, row, label + " ->")
	if await _place(b, row):
		await _walk(a, row, label + " <-")


func _body_cell() -> float:
	return (_player.global_position.x + _body_x * _scale) / (CELL * _scale)


func _feet_row() -> float:
	return (_player.global_position.y + _sole_y * _scale) / (CELL * _scale)


## Start cells can be a ladder hole; a run is still checked from the other end.
func _place(cell_x: float, row: float) -> bool:
	for action in ACTIONS:
		Input.action_release(action)
	var pos := Vector2(
		(cell_x * CELL - _body_x) * _scale,
		(row * CELL - _sole_y) * _scale - 2.0
	)
	_player.call("respawn", pos)
	for _i in 12:
		await physics_frame
	return absf(_feet_row() - row) < 0.05 and _player.is_on_floor()


func _walk(to_cell: float, row: float, label: String) -> void:
	var sgn := signf(to_cell - _body_cell())
	var action := "move_right" if sgn > 0.0 else "move_left"
	var budget := int(absf(to_cell - _body_cell()) / 6.0 * 60.0) + 90
	var best := _body_cell() * sgn
	var stall := 0
	Input.action_press(action)
	for _i in budget:
		await physics_frame
		var x := _body_cell()
		var dy := _feet_row() - row
		if dy > SINK_CELLS or dy < -RISE_CELLS:
			var what := "on the rope" if _player.on_rope else "through the floor"
			_fail("%s: dropped %s at cell %.2f, feet row %.2f" % [label, what, x, _feet_row()])
			break
		if _player.on_ladder:
			_fail("%s: grabbed a ladder at cell %.2f" % [label, x])
			break
		if x * sgn > best + 0.01:
			best = x * sgn
			stall = 0
		else:
			stall += 1
		if stall >= STALL_FRAMES:
			_fail("%s: stuck at cell %.2f, feet row %.2f" % [label, x, _feet_row()])
			break
		if (x - to_cell) * sgn >= 0.0:
			break
	Input.action_release(action)


func _fail(message: String) -> void:
	_problems += 1
	push_error("walk_audit: " + message)
