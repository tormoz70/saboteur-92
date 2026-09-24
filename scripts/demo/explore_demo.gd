extends Node
## Maze explorer: drives Nina over the whole collision maze with real inputs,
## sped up. Graph comes from tools/explore/build_nav.py (floors, ladders,
## somersaults, ledge drops, lifts). Nina heads for the nearest waypoint she
## has not stood on yet; every waypoint her feet pass is marked; a move that
## fails twice is dropped and the route is planned again. Ends when nothing
## unvisited is reachable and writes a report for tools/explore/nav_reach.py.
##
## Start: `--demo-explore`, or add this script to Level01 at runtime (MCP
## run_script). Guards, the bomb console and the alarm are switched off.

enum Edge { WALK, CLIMB, JUMP, DROP, LIFT, PASSAGE }
enum Phase { PLAN, APPROACH, ACT, AIR, SETTLE }

const ARG := "--demo-explore"
const GRAPH_PATH := "res://.mcp/explore/nav_graph.json"
const REPORT_PATH := "res://.mcp/explore/explore_report.json"
const ACTIONS := ["move_left", "move_right", "move_up", "move_down", "jump", "punch"]
const SPEED_UP := 12
const FEET_NATIVE := 56.0
const BODY_X_NATIVE := 24.0
const VISIT_DX := 12.0
const MAX_EDGE_FAILS := 2
const MAX_TARGET_TRIES := 3
const LOCATE_DX := 20.0
const LOG_EVERY := 5.0

var speed_up := SPEED_UP
var done := false
var summary := ""

var _player: CharacterBody2D
var _scale := 2.0
var _nx := PackedFloat32Array()
var _nf := PackedFloat32Array()
var _crouch := PackedByteArray()
var _visited := PackedByteArray()
var _adj: Array = []
var _ea := PackedInt32Array()
var _eb := PackedInt32Array()
var _et := PackedInt32Array()
var _ex := PackedFloat32Array()
var _edge_fail: Dictionary = {}
var _target_tries: Dictionary = {}
var _given_up: Dictionary = {}
var _rows: Dictionary = {}
var _lifts: Array = []

var _path: Array = []
var _edge := -1
var _phase: Phase = Phase.PLAN
var _phase_t := 0.0
var _edge_t := 0.0
var _edge_budget := 0.0
var _left_floor := false
var _target := -1
var _elapsed := 0.0
var _log_t := 0.0
var _ok := [0, 0, 0, 0, 0, 0]
var _bad := [0, 0, 0, 0, 0, 0]
var _rescues := 0
var _lost_t := 0.0
var _visited_n := 0
var _traps: Array = []
var _stuck_spots: Array = []


func _ready() -> void:
	var level := get_parent()
	# In the level scene it only wakes up for the flag; run_script adds it
	# with the "manual" meta set.
	if not OS.get_cmdline_user_args().has(ARG) and not has_meta("manual"):
		queue_free()
		return
	process_physics_priority = -100
	_player = level.get_node_or_null("Player") as CharacterBody2D
	if _player == null or not _load_graph():
		summary = "explorer: player or graph missing"
		push_error("[Explore] %s" % summary)
		queue_free()
		return
	_scale = _player.scale.x
	_quiet_world(level)
	_collect_lifts(level)
	Engine.max_physics_steps_per_frame = speed_up * 2
	Engine.physics_ticks_per_second = 60 * speed_up
	Engine.time_scale = float(speed_up)
	print("[Explore] start: %d waypoints, %d moves, x%d" % [_nx.size(), _ea.size(), speed_up])


func _exit_tree() -> void:
	Engine.time_scale = 1.0
	Engine.physics_ticks_per_second = 60
	Engine.max_physics_steps_per_frame = 8
	_release_all()


# --- setup -------------------------------------------------------------------

func _load_graph() -> bool:
	if not FileAccess.file_exists(GRAPH_PATH):
		return false
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(GRAPH_PATH))
	if typeof(data) != TYPE_DICTIONARY:
		return false
	var nodes: Array = data["nodes"]
	_nx.resize(nodes.size())
	_nf.resize(nodes.size())
	_crouch.resize(nodes.size())
	_visited.resize(nodes.size())
	_adj.resize(nodes.size())
	for i in nodes.size():
		var n: Array = nodes[i]
		_nx[i] = float(n[0])
		_nf[i] = float(n[1])
		_crouch[i] = int(n[2])
		_adj[i] = PackedInt32Array()
		var row := int(n[1])
		var ids: PackedInt32Array = _rows.get(row, PackedInt32Array())
		ids.append(i)
		_rows[row] = ids
	var edges: Array = data["edges"]
	_ea.resize(edges.size())
	_eb.resize(edges.size())
	_et.resize(edges.size())
	_ex.resize(edges.size())
	for i in edges.size():
		var e: Array = edges[i]
		_ea[i] = int(e[0])
		_eb[i] = int(e[1])
		_et[i] = int(e[2])
		_ex[i] = float(e[3])
		var list: PackedInt32Array = _adj[_ea[i]]
		list.append(i)
		_adj[_ea[i]] = list
	_lifts = data.get("lifts", [])
	return true


func _quiet_world(level: Node) -> void:
	GameManager.demo_mode = true
	GameManager.lives = 99
	for label in GameManager.LIFT_CODE_LABELS:
		GameManager.note_code(label)
	# raise_alarm() returns early once alarmed, so no alarm guard spawns.
	GameManager.alarmed = true
	for node_name in ["Guards", "SabotageTarget", "ExitZone"]:
		var node := level.get_node_or_null(node_name)
		if node == null:
			continue
		node.process_mode = Node.PROCESS_MODE_DISABLED
		if node is CanvasItem:
			(node as CanvasItem).visible = false
		if node is Area2D:
			(node as Area2D).set_deferred("monitoring", false)


func _collect_lifts(level: Node) -> void:
	var cabins := level.get_tree().get_nodes_in_group("lifts")
	for sh in _lifts:
		var list: Array = []
		for cabin in cabins:
			if absf((cabin as Node2D).global_position.x - float(sh["x"]) * _scale) < 2.0:
				list.append(cabin)
		sh["cabins"] = list


# --- main loop ---------------------------------------------------------------

func _physics_process(delta: float) -> void:
	if done or not is_instance_valid(_player):
		return
	if GameManager.state != GameManager.GameState.PLAYING:
		_finish("game state %d" % int(GameManager.state))
		return
	_elapsed += delta
	_mark_visited()
	_log_t += delta
	if _log_t >= LOG_EVERY:
		_log_t = 0.0
		_log_progress()
	if _edge < 0:
		_plan()
		return
	_edge_t += delta
	_phase_t += delta
	if _edge_t > _edge_budget:
		_end_edge(false, "timeout")
		return
	match _et[_edge]:
		Edge.WALK:
			_run_walk()
		Edge.CLIMB:
			_run_climb()
		Edge.JUMP:
			_run_jump()
		Edge.DROP:
			_run_drop()
		Edge.LIFT:
			_run_lift()
		_:
			_end_edge(false, "unsupported")


func _feet() -> Vector2:
	var p := _player.global_position
	return Vector2(p.x / _scale + BODY_X_NATIVE, p.y / _scale + FEET_NATIVE)


func _mark_visited() -> void:
	if not _player.is_on_floor() or _player.on_ladder:
		return
	var ft := _feet()
	for row in [int(ft.y) - 8, int(ft.y), int(ft.y) + 8]:
		var snapped := int(round(float(row) / 8.0)) * 8
		if not _rows.has(snapped):
			continue
		for i in (_rows[snapped] as PackedInt32Array):
			if _visited[i] == 0 and absf(_nx[i] - ft.x) <= VISIT_DX and absf(_nf[i] - ft.y) <= 6.0:
				_visited[i] = 1
				_visited_n += 1


func _locate() -> int:
	if not _player.is_on_floor() or _player.on_ladder:
		return -1
	var ft := _feet()
	var best := -1
	var best_d := LOCATE_DX
	for row in [int(ft.y) - 8, int(ft.y), int(ft.y) + 8]:
		var snapped := int(round(float(row) / 8.0)) * 8
		if not _rows.has(snapped):
			continue
		for i in (_rows[snapped] as PackedInt32Array):
			var d := absf(_nx[i] - ft.x) + absf(_nf[i] - ft.y)
			if d < best_d:
				best_d = d
				best = i
	return best


# --- planning ----------------------------------------------------------------

func _plan() -> void:
	_release_all()
	if _path.is_empty():
		var here := _locate()
		if here < 0:
			_lost_t += get_physics_process_delta_time()
			if _lost_t > 3.0:
				_rescue()
			return
		_lost_t = 0.0
		_path = _route_to_nearest_unvisited(here)
		if _path.is_empty():
			if not _escape_trap(here):
				_finish("nothing reachable left")
			return
	_edge = int(_path.pop_front())
	_edge_t = 0.0
	_phase_t = 0.0
	_phase = Phase.APPROACH
	_left_floor = false
	_edge_budget = 6.0 + _cost(_edge) * 3.0


func _cost(e: int) -> float:
	var a := _ea[e]
	var b := _eb[e]
	var dx := absf(_nx[b] - _nx[a])
	var df := absf(_nf[b] - _nf[a])
	match _et[e]:
		Edge.WALK:
			return dx / (50.0 if _crouch[a] or _crouch[b] else 55.0)
		Edge.CLIMB:
			return df / 28.0 + 1.0
		Edge.JUMP:
			return 2.0 + dx / 90.0
		Edge.DROP:
			return 1.0 + df / 200.0
		Edge.LIFT:
			return df / 44.0 + 3.0
	return 5.0


func _edge_usable(e: int) -> bool:
	if int(_edge_fail.get(e, 0)) >= MAX_EDGE_FAILS:
		return false
	if _et[e] == Edge.LIFT:
		return _cabin_at(e) != null
	return true


func _cabin_at(e: int) -> Node2D:
	var sh: Dictionary = _lifts[int(_ex[e])]
	var from_y := _nf[_ea[e]] * _scale
	for cabin in sh.get("cabins", []):
		var c := cabin as Node2D
		if int(c.get("dir")) == 0 and absf(c.global_position.y - from_y) <= 8.0:
			return c
	return null


func _route_to_nearest_unvisited(start: int) -> Array:
	var n := _nx.size()
	var dist := PackedFloat64Array()
	dist.resize(n)
	dist.fill(INF)
	var via := PackedInt32Array()
	via.resize(n)
	via.fill(-1)
	dist[start] = 0.0
	var heap: Array = [[0.0, start]]
	var goal := -1
	while not heap.is_empty():
		var top: Array = _heap_pop(heap)
		var d: float = top[0]
		var a: int = top[1]
		if d > dist[a]:
			continue
		if a != start and _visited[a] == 0 and not _given_up.has(a):
			goal = a
			break
		for e in (_adj[a] as PackedInt32Array):
			if not _edge_usable(e):
				continue
			var b := _eb[e]
			var nd := d + _cost(e)
			if nd < dist[b]:
				dist[b] = nd
				via[b] = e
				_heap_push(heap, [nd, b])
	if goal < 0:
		return []
	var tries := int(_target_tries.get(goal, 0)) + 1
	_target_tries[goal] = tries
	if tries > MAX_TARGET_TRIES:
		_given_up[goal] = true
		return _route_to_nearest_unvisited(start)
	_target = goal
	var path: Array = []
	var cur := goal
	while cur != start:
		var e := via[cur]
		path.push_front(e)
		cur = _ea[e]
	return path


func _heap_push(heap: Array, item: Array) -> void:
	heap.append(item)
	var i := heap.size() - 1
	while i > 0:
		var p := (i - 1) / 2
		if heap[p][0] <= heap[i][0]:
			break
		var t: Array = heap[p]
		heap[p] = heap[i]
		heap[i] = t
		i = p


func _heap_pop(heap: Array) -> Array:
	var top: Array = heap[0]
	var last: Array = heap.pop_back()
	if heap.is_empty():
		return top
	heap[0] = last
	var i := 0
	while true:
		var l := i * 2 + 1
		var r := l + 1
		var m := i
		if l < heap.size() and heap[l][0] < heap[m][0]:
			m = l
		if r < heap.size() and heap[r][0] < heap[m][0]:
			m = r
		if m == i:
			break
		var t: Array = heap[m]
		heap[m] = heap[i]
		heap[i] = t
		i = m
	return top


func _end_edge(ok: bool, why: String = "") -> void:
	var t := _et[_edge]
	if ok:
		_ok[t] += 1
	else:
		_bad[t] += 1
		_edge_fail[_edge] = int(_edge_fail.get(_edge, 0)) + 1
		var a := _ea[_edge]
		var b := _eb[_edge]
		print(
			"[Explore] %s failed (%s) (%.0f,%.0f)->(%.0f,%.0f) at feet %s"
			% [Edge.keys()[t], why, _nx[a], _nf[a], _nx[b], _nf[b], _feet().round()]
		)
		_path.clear()
	_edge = -1
	_release_all()


## Nothing new is reachable from here, but other visited spots still lead on:
## this corner is a one-way trap. Log it and carry Nina to the nearest
## visited waypoint that still has somewhere new to go.
func _escape_trap(here: int) -> bool:
	var leads_on := _nodes_leading_to_unvisited()
	var ft := Vector2(_nx[here], _nf[here])
	var best := -1
	var best_d := INF
	for i in _nx.size():
		if _visited[i] == 0 or i == here or leads_on[i] == 0:
			continue
		var d := Vector2(_nx[i], _nf[i]).distance_squared_to(ft)
		if d < best_d:
			best_d = d
			best = i
	if best < 0:
		return false
	_traps.append([_nx[here], _nf[here]])
	_teleport_to(best)
	print(
		"[Explore] trap at (%.0f,%.0f): no way on; carried to (%.0f,%.0f)"
		% [ft.x, ft.y, _nx[best], _nf[best]]
	)
	return true


## 1 for every node with a usable route to an unvisited waypoint.
func _nodes_leading_to_unvisited() -> PackedByteArray:
	var n := _nx.size()
	var radj: Array = []
	radj.resize(n)
	for i in n:
		radj[i] = PackedInt32Array()
	for e in _ea.size():
		if _edge_usable(e):
			var list: PackedInt32Array = radj[_eb[e]]
			list.append(_ea[e])
			radj[_eb[e]] = list
	var mark := PackedByteArray()
	mark.resize(n)
	var stack: Array = []
	for i in n:
		if _visited[i] == 0 and not _given_up.has(i):
			stack.append(i)
	while not stack.is_empty():
		var b: int = stack.pop_back()
		for a in (radj[b] as PackedInt32Array):
			if mark[a] == 0:
				mark[a] = 1
				stack.append(a)
	return mark


func _teleport_to(i: int) -> void:
	_rescues += 1
	_player.set("on_ladder", false)
	_player.call("apply_world_mask")
	_player.global_position = Vector2(
		(_nx[i] - BODY_X_NATIVE) * _scale, (_nf[i] - FEET_NATIVE) * _scale - 2.0
	)
	_player.velocity = Vector2.ZERO
	_player.reset_physics_interpolation()
	_path.clear()


func _rescue() -> void:
	# Wedged off the graph (mid-ladder, in a pit): put Nina back on the
	# nearest waypoint she already stood on. Counted in the report.
	_lost_t = 0.0
	var ft := _feet()
	var best := -1
	var best_d := INF
	for i in _nx.size():
		if _visited[i] == 0:
			continue
		var d := Vector2(_nx[i], _nf[i]).distance_squared_to(ft)
		if d < best_d:
			best_d = d
			best = i
	if best < 0:
		best = 0
	print("[Explore] rescue from %s to (%.0f,%.0f)" % [ft.round(), _nx[best], _nf[best]])
	_stuck_spots.append([ft.x, ft.y])
	_teleport_to(best)


# --- move executors ----------------------------------------------------------

func _near_x(x: float, tol: float = 3.0) -> bool:
	return absf(_feet().x - x) <= tol


func _steer_to(x: float, crawl: bool = false) -> bool:
	var dx := x - _feet().x
	if absf(dx) <= 3.0:
		_release_all()
		return true
	var dir := "move_right" if dx > 0.0 else "move_left"
	if crawl:
		_press_set([dir, "move_down"])
	else:
		_press_set([dir])
	return false


func _arrived(b: int, tol_x: float = 6.0) -> bool:
	var ft := _feet()
	return (
		_player.is_on_floor()
		and not _player.on_ladder
		and absf(ft.x - _nx[b]) <= tol_x
		and absf(ft.y - _nf[b]) <= 10.0
	)


func _run_walk() -> void:
	var a := _ea[_edge]
	var b := _eb[_edge]
	var crawl := _crouch[a] == 1 or _crouch[b] == 1
	var reached := _steer_to(_nx[b], crawl)
	if not _player.is_on_floor() and not _player.on_ladder:
		_left_floor = true
		return
	if _left_floor:
		# Walked off something the graph thought was floor.
		_end_edge(_arrived(b, 12.0), "fell")
		return
	if reached or _arrived(b, 4.0):
		_end_edge(absf(_feet().y - _nf[b]) <= 10.0, "wrong floor")


func _run_climb() -> void:
	var b := _eb[_edge]
	var lx := _ex[_edge] + 0.0
	var up := _nf[b] < _nf[_ea[_edge]]
	match _phase:
		Phase.APPROACH:
			if _steer_to(lx):
				_phase = Phase.ACT
				_phase_t = 0.0
		Phase.ACT:
			var ft := _feet()
			if up:
				if ft.y <= _nf[b] + 2.0:
					_release_all()
					_phase = Phase.SETTLE
					_phase_t = 0.0
					return
				_press_set(["move_up"])
			else:
				_press_set(["move_down"])
				if _phase_t > 0.3 and _player.is_on_floor() and not _player.on_ladder:
					if ft.y >= _nf[b] - 10.0:
						_phase = Phase.SETTLE
						_phase_t = 0.0
					elif _phase_t > 2.0:
						_end_edge(false, "no descent")
		Phase.SETTLE:
			_release_all()
			# Idle at the foot of a ladder still counts as on_ladder.
			var ft2 := _feet()
			if absf(ft2.x - _nx[b]) <= 16.0 and absf(ft2.y - _nf[b]) <= 10.0 and _phase_t > 0.2:
				_end_edge(true)
			elif _phase_t > 1.5:
				_end_edge(false, "no landing")


func _run_jump() -> void:
	var a := _ea[_edge]
	var b := _eb[_edge]
	var d := 1.0 if _ex[_edge] > 0.0 else -1.0
	var dir := "move_right" if d > 0.0 else "move_left"
	match _phase:
		Phase.APPROACH:
			# Back off a little so Nina is running at the takeoff point.
			if _steer_to(_nx[a] - d * 12.0, _crouch[a] == 1):
				_phase = Phase.ACT
				_phase_t = 0.0
		Phase.ACT:
			if not _player.is_on_floor():
				_phase = Phase.AIR
				_phase_t = 0.0
				return
			var past := (_feet().x - _nx[a]) * d
			if past >= -1.0:
				_press_set([dir, "move_up"])
			else:
				_press_set([dir])
			if past > 20.0:
				_end_edge(false, "no takeoff")
		Phase.AIR:
			_press_set([])
			if _player.is_on_floor() or _player.on_ladder:
				_phase = Phase.SETTLE
				_phase_t = 0.0
		Phase.SETTLE:
			_release_all()
			if _phase_t < 0.1:
				return
			_end_edge(_arrived(b, 40.0), "landed elsewhere")


func _run_drop() -> void:
	var b := _eb[_edge]
	var dir := "move_right" if _ex[_edge] > 0.0 else "move_left"
	match _phase:
		Phase.APPROACH:
			_press_set([dir])
			if not _player.is_on_floor():
				_phase = Phase.AIR
				_phase_t = 0.0
			elif _phase_t > 1.5:
				_end_edge(false, "edge is a wall")
		Phase.AIR:
			_press_set([])
			if _player.is_on_floor() or _player.on_ladder:
				_phase = Phase.SETTLE
				_phase_t = 0.0
		Phase.SETTLE:
			_release_all()
			if _phase_t < 0.1:
				return
			_end_edge(_arrived(b, 40.0), "landed elsewhere")


func _run_lift() -> void:
	var b := _eb[_edge]
	var sh: Dictionary = _lifts[int(_ex[_edge])]
	var cx := float(sh["center"])
	var up := _nf[b] < _nf[_ea[_edge]]
	match _phase:
		Phase.APPROACH:
			if _steer_to(cx) and _player.on_lift:
				_phase = Phase.ACT
				_phase_t = 0.0
		Phase.ACT:
			_press_set(["move_up" if up else "move_down"])
			if _player.is_riding_lift():
				_phase = Phase.AIR
				_phase_t = 0.0
			elif _phase_t > 1.0:
				_end_edge(false, "cabin did not start")
		Phase.AIR:
			_press_set([])
			if not _player.is_riding_lift() and _phase_t > 0.3:
				_phase = Phase.SETTLE
				_phase_t = 0.0
		Phase.SETTLE:
			_release_all()
			if _phase_t < 0.2:
				return
			_end_edge(_arrived(b, 24.0), "stopped elsewhere")


# --- input -------------------------------------------------------------------

func _press_set(wanted: Array) -> void:
	for action in ACTIONS:
		if action in wanted:
			if not Input.is_action_pressed(action):
				Input.action_press(action)
		elif Input.is_action_pressed(action):
			Input.action_release(action)


func _release_all() -> void:
	_press_set([])


# --- report ------------------------------------------------------------------

func coverage() -> Dictionary:
	return {
		"elapsed": _elapsed,
		"visited": _visited_n,
		"nodes": _nx.size(),
		"ok": _ok,
		"bad": _bad,
		"rescues": _rescues,
		"feet": _feet(),
		"target": _target,
		"done": done,
	}


func _log_progress() -> void:
	print(
		"[Explore] t=%.0fs visited %d/%d ok=%s bad=%s rescues=%d feet=%s"
		% [_elapsed, _visited_n, _nx.size(), _ok, _bad, _rescues, _feet().round()]
	)


func _finish(reason: String) -> void:
	done = true
	_release_all()
	var visited: Array = []
	for i in _visited.size():
		if _visited[i] == 1:
			visited.append(i)
	var failed: Array = []
	for e in _edge_fail:
		failed.append(
			[Edge.keys()[_et[e]], _nx[_ea[e]], _nf[_ea[e]], _nx[_eb[e]], _nf[_eb[e]], _edge_fail[e]]
		)
	var report := {
		"reason": reason,
		"elapsed": _elapsed,
		"visited": visited,
		"failed_moves": failed,
		"given_up": _given_up.keys(),
		"traps": _traps,
		"stuck": _stuck_spots,
		"ok": _ok,
		"bad": _bad,
		"rescues": _rescues,
	}
	var f := FileAccess.open(REPORT_PATH, FileAccess.WRITE)
	if f:
		f.store_string(JSON.stringify(report))
	summary = (
		"%s: visited %d/%d in %.0fs game time, moves ok=%s bad=%s, rescues=%d"
		% [reason, _visited_n, _nx.size(), _elapsed, _ok, _bad, _rescues]
	)
	print("[Explore] done — %s" % summary)
	Engine.time_scale = 1.0
	Engine.physics_ticks_per_second = 60
	if OS.get_cmdline_user_args().has(ARG):
		get_tree().quit()
