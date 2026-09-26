class_name ChunkValidator
extends RefCounted

## Lightweight, build-free validation for world chunks in the JSON schema
## (docs/world_chunk_schema.json). Because the schema keeps a dedicated
## `collision` layer whose palette carries semantic types
## (empty/solid/ladder/oneway/rope), we can reason about reachability directly
## on the integer grid — no scene instantiation, no physics server.
##
## Why this matters for the AI generator: an LLM proposes a chunk, we run
## validate_chunk_connectivity() in microseconds, and reject/repair it BEFORE
## ever building a Node. This is the cheap gate in a generate-check-repair loop.
##
## Reachability model (a pragmatic platformer approximation, not a full physics
## sim): a cell is "standable" if it is non-solid and either is a climbable
## (ladder/rope) or has support directly below (solid/oneway/ladder) or is the
## floor edge. From a standable cell the agent may:
##   * walk left/right to an adjacent standable cell,
##   * climb up/down through ladder/rope cells,
##   * fall straight down through empty cells until it lands.
## This catches the common "no path from entry to exit" and "sealed pocket"
## failures without pretending to model jump arcs precisely.

# Semantic collision types (mirror scripts/world/tilemap_utils.gd constants).
const T_EMPTY := "empty"
const T_SOLID := "solid"
const T_LADDER := "ladder"
const T_ONEWAY := "oneway"
const T_ROPE := "rope"

# Max jump height in cells the model allows when stepping up onto a ledge.
const MAX_STEP_UP := 1


## Validate structure + solvability. Returns:
##   { ok: bool, errors: PackedStringArray, reachable: bool,
##     unreachable_exits: Array }
## `entries` / `exits` are arrays of [x, y] cell coordinates. If omitted, the
## function derives them from the chunk's entities (type "spawn" as entry,
## "exit" as exit).
static func validate_chunk_connectivity(chunk_data: Dictionary,
		id_map: Dictionary, entries: Array = [], exits: Array = []) -> Dictionary:
	var result := {
		"ok": false,
		"errors": PackedStringArray(),
		"reachable": false,
		"unreachable_exits": [],
	}
	var errors: PackedStringArray = result["errors"]

	# --- structural checks --------------------------------------------------
	var grid_size: Array = chunk_data.get("grid_size", [0, 0])
	if grid_size.size() != 2 or int(grid_size[0]) <= 0 or int(grid_size[1]) <= 0:
		errors.append("grid_size missing or invalid")
		return result
	var width := int(grid_size[0])
	var height := int(grid_size[1])

	var types := _collision_type_grid(chunk_data, id_map, width, height)
	if types.is_empty():
		errors.append("no 'collision' layer — cannot assess walkability")
		return result

	# Derive entry/exit points from entities if none were supplied.
	if entries.is_empty():
		entries = _entity_cells(chunk_data, "spawn")
	if exits.is_empty():
		exits = _entity_cells(chunk_data, "exit")
	if entries.is_empty():
		errors.append("no entry points (pass `entries` or add a 'spawn' entity)")
	if exits.is_empty():
		errors.append("no exit points (pass `exits` or add an 'exit' entity)")
	if not entries.is_empty() and not exits.is_empty():
		var reach := _flood_reachable(types, width, height, entries)
		var missed: Array = []
		for e in exits:
			var ex := int(e[0])
			var ey := int(e[1])
			if not _cell_reachable(reach, width, height, ex, ey):
				missed.append([ex, ey])
		result["reachable"] = missed.is_empty()
		result["unreachable_exits"] = missed
		if not missed.is_empty():
			errors.append("%d/%d exit(s) unreachable from entries"
				% [missed.size(), exits.size()])

	result["ok"] = errors.is_empty()
	return result


# --- collision grid ---------------------------------------------------------

## Build a width*height PackedStringArray of collision type names from the
## chunk's collision layer + the id map's collision palette.
static func _collision_type_grid(chunk_data: Dictionary, id_map: Dictionary,
		width: int, height: int) -> PackedStringArray:
	var chunk_layers: Dictionary = chunk_data.get("layers", {})
	if not chunk_layers.has("collision"):
		return PackedStringArray()
	var palettes: Dictionary = id_map.get("palettes", {})
	var layers_cfg: Dictionary = id_map.get("layers", {})
	var pal_key := str(layers_cfg.get("collision", {}).get("palette", "s2_collision_tileset"))
	var col_types: Array = palettes.get(pal_key, {}).get("collision_types", [])
	var empty_id := int(chunk_data.get("empty_id", id_map.get("empty_id", -1)))

	var flat := _decode_layer_ids(chunk_layers["collision"], width, height, empty_id)
	var out := PackedStringArray()
	out.resize(width * height)
	for i in out.size():
		var pid := flat[i]
		if pid == empty_id or pid < 0 or pid >= col_types.size():
			out[i] = T_EMPTY
		else:
			out[i] = str(col_types[pid])
	return out


## Decode a schema layer entry ("grid" or "rle") into a flat id array.
static func _decode_layer_ids(layer_data: Dictionary, width: int, height: int,
		empty_id: int) -> PackedInt32Array:
	var out := PackedInt32Array()
	out.resize(width * height)
	out.fill(empty_id)
	var data: Array = layer_data.get("data", [])
	if str(layer_data.get("encoding", "grid")) == "rle":
		var i := 0
		var pos := 0
		while i + 1 < data.size():
			var value := int(data[i])
			var count := int(data[i + 1])
			for _n in count:
				if pos >= out.size():
					break
				out[pos] = value
				pos += 1
			i += 2
	else:
		for y in mini(height, data.size()):
			var row: Array = data[y]
			for x in mini(width, row.size()):
				out[y * width + x] = int(row[x])
	return out


# --- reachability -----------------------------------------------------------

static func _is_solid(t: String) -> bool:
	return t == T_SOLID or t == T_ONEWAY


static func _is_climb(t: String) -> bool:
	return t == T_LADDER or t == T_ROPE


static func _at(types: PackedStringArray, w: int, h: int, x: int, y: int) -> String:
	if x < 0 or y < 0 or x >= w or y >= h:
		return T_SOLID  # treat out-of-bounds as wall for in-chunk checks
	return types[y * w + x]


## A cell an agent can occupy while "standing" (feet there).
static func _standable(types: PackedStringArray, w: int, h: int, x: int, y: int) -> bool:
	var here := _at(types, w, h, x, y)
	if _is_solid(here):
		return false
	if _is_climb(here):
		return true
	# supported by ground below (solid, one-way, or a ladder top)
	var below := _at(types, w, h, x, y + 1)
	return _is_solid(below) or below == T_LADDER


## BFS flood from all entries; returns a byte grid (1 = reachable).
static func _flood_reachable(types: PackedStringArray, w: int, h: int,
		entries: Array) -> PackedByteArray:
	var seen := PackedByteArray()
	seen.resize(w * h)
	var queue: Array[Vector2i] = []
	for e in entries:
		var sx := int(e[0])
		var sy := int(e[1])
		var start := _settle(types, w, h, sx, sy)
		if start.x >= 0 and seen[start.y * w + start.x] == 0:
			seen[start.y * w + start.x] = 1
			queue.append(start)

	while not queue.is_empty():
		var c: Vector2i = queue.pop_back()
		for n in _neighbors(types, w, h, c.x, c.y):
			var idx := n.y * w + n.x
			if seen[idx] == 0:
				seen[idx] = 1
				queue.append(n)
	return seen


## Drop a raw entry point down to the first standable cell (entities are often
## authored a little above the floor).
static func _settle(types: PackedStringArray, w: int, h: int, x: int, y: int) -> Vector2i:
	if x < 0 or x >= w:
		return Vector2i(-1, -1)
	var yy := clampi(y, 0, h - 1)
	while yy < h:
		if _standable(types, w, h, x, yy):
			return Vector2i(x, yy)
		yy += 1
	return Vector2i(-1, -1)


static func _neighbors(types: PackedStringArray, w: int, h: int,
		x: int, y: int) -> Array[Vector2i]:
	var out: Array[Vector2i] = []
	var here := _at(types, w, h, x, y)

	# Walk left / right (allow small step up onto a ledge, or step down).
	for dx in [-1, 1]:
		var nx := x + dx
		if _is_solid(_at(types, w, h, nx, y)):
			# blocked at head height — try stepping up MAX_STEP_UP
			for up in range(1, MAX_STEP_UP + 1):
				if not _is_solid(_at(types, w, h, nx, y - up)) \
						and _standable(types, w, h, nx, y - up):
					out.append(Vector2i(nx, y - up))
					break
			continue
		if _standable(types, w, h, nx, y):
			out.append(Vector2i(nx, y))
		else:
			# no ground: fall to the first standable cell below
			var landed := _settle(types, w, h, nx, y)
			if landed.x >= 0:
				out.append(landed)

	# Climb up / down on ladders & ropes.
	if _is_climb(here) or _is_climb(_at(types, w, h, x, y + 1)):
		if _is_climb(_at(types, w, h, x, y - 1)) or _standable(types, w, h, x, y - 1):
			out.append(Vector2i(x, y - 1))
	if _is_climb(_at(types, w, h, x, y + 1)):
		out.append(Vector2i(x, y + 1))

	# Fall straight down through empty space.
	var down := _at(types, w, h, x, y + 1)
	if down == T_EMPTY:
		var landed := _settle(types, w, h, x, y + 1)
		if landed.x >= 0:
			out.append(landed)
	return out


static func _cell_reachable(seen: PackedByteArray, w: int, h: int, x: int, y: int) -> bool:
	# An exit counts as reached if the exit cell OR the standable cell it
	# settles onto is flagged (exits are often drawn floating in a doorway).
	if x < 0 or y < 0 or x >= w or y >= h:
		return false
	if seen[y * w + x] == 1:
		return true
	var yy := y
	while yy < h:
		if seen[yy * w + x] == 1:
			return true
		yy += 1
	return false


static func _entity_cells(chunk_data: Dictionary, etype: String) -> Array:
	var out: Array = []
	for spec in chunk_data.get("entities", []):
		if typeof(spec) == TYPE_DICTIONARY and str(spec.get("type", "")) == etype:
			var p: Array = spec.get("position", [])
			if p.size() >= 2:
				out.append([int(round(float(p[0]))), int(round(float(p[1])))])
	return out
