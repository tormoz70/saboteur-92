class_name ChunkValidator
extends RefCounted

## Lightweight, build-free validation for world chunks in the JSON schema
## (docs/world_chunk_schema.json). Because the schema keeps a dedicated
## `collision` layer whose palette carries semantic types
## (empty/solid/ladder/oneway/rope), we can reason about reachability directly
## on the integer grid — no scene instantiation, no physics server.
##
## Why this matters for the AI generator: an LLM proposes a chunk, we run
## validate_chunk_connectivity() (~25 ms per 128x72 chunk), and reject/repair
## it BEFORE ever building a Node. This is the cheap gate in a
## generate-check-repair loop.
##
## Structural checks: known layer keys, well-formed "grid"/"rle" payloads that
## cover exactly width*height cells, and palette ids inside their palette.
##
## Reachability model (a platformer approximation, not a physics sim). The
## agent is the player's body box, `agent_width` x `agent_height` cells
## (`crouch_height` while crawling), anchored at its bottom-left "feet" cell:
##   * solid blocks the body; oneway only supports from above (the body passes
##     through it upwards and sideways); ladder/rope never block;
##   * it stands where the crouched body fits and something supports it
##     (solid, oneway or a ladder top below), or while holding a ladder/rope —
##     on ladders the body ignores collisions, as LadderController does;
##   * it walks/crawls one cell sideways, falls straight down until it lands,
##     climbs ladders/ropes, and jumps: rises up to `jump_up` cells, then moves
##     up to `jump_across` cells sideways at that height and falls;
##   * a solid slab at most `hatch_thickness` cells thick right above/below a
##     ladder is a hatch: the agent climbs through it (LadderController lets
##     Nina pass lids up to RUNG_PAD_NATIVE = 20 px);
##   * `links` add teleports (lifts, passages): [[[x1, y1], [x2, y2]], ...],
##     traversable both ways.
## Out-of-chunk cells count as solid on the sides and bottom and as open sky
## above, so an entry near the top edge still fits.

# Player body (player.gd BODY_STAND_SIZE 14x42, BODY_CROUCH_SIZE 14x24 native
# px) and a plain jump (jump_velocity -270, gravity 820, speed 110 at
# level_scale 2: ~22 px up, ~36 px across) in 8 px cells.
const DEFAULT_OPTIONS := {
	"agent_width": 2,
	"agent_height": 6,
	"crouch_height": 3,
	"jump_up": 2,
	"jump_across": 4,
	"hatch_thickness": 2,
	"links": [],
}

const TYPE_CODES := {
	"empty": TileMapUtils.TILE_EMPTY,
	"solid": TileMapUtils.TILE_SOLID,
	"ladder": TileMapUtils.TILE_LADDER,
	"oneway": TileMapUtils.TILE_ONEWAY,
	"rope": TileMapUtils.TILE_ROPE,
}


## Validate structure + solvability. Returns:
##   { ok: bool, errors: PackedStringArray, reachable: bool,
##     unreachable_exits: Array }
## `entries` / `exits` are arrays of [x, y] cell coordinates (points the body
## must touch). If omitted, they come from the chunk's entities: "spawn" as
## entry (its sprite top-left origin is converted to the feet), "exit" as exit.
## `options` overrides DEFAULT_OPTIONS.
static func validate_chunk_connectivity(chunk_data: Dictionary,
		id_map: Dictionary, entries: Array = [], exits: Array = [],
		options: Dictionary = {}) -> Dictionary:
	var result := {
		"ok": false,
		"errors": PackedStringArray(),
		"reachable": false,
		"unreachable_exits": [],
	}
	var errors: PackedStringArray = result["errors"]
	var opts := DEFAULT_OPTIONS.duplicate()
	opts.merge(options, true)

	# --- structural checks --------------------------------------------------
	var grid_size: Array = chunk_data.get("grid_size", [0, 0])
	if grid_size.size() != 2 or int(grid_size[0]) <= 0 or int(grid_size[1]) <= 0:
		errors.append("grid_size missing or invalid")
		return result
	var width := int(grid_size[0])
	var height := int(grid_size[1])
	var empty_id := int(chunk_data.get("empty_id", id_map.get("empty_id", -1)))

	var layers_cfg: Dictionary = id_map.get("layers", {})
	var palettes: Dictionary = id_map.get("palettes", {})
	var chunk_layers: Dictionary = chunk_data.get("layers", {})
	var collision_ids := PackedInt32Array()
	for key in chunk_layers:
		if not layers_cfg.has(key):
			errors.append("unknown layer '%s'" % key)
			continue
		var tiles: Array = palettes.get(str(layers_cfg[key].get("palette", "")), {}).get("tiles", [])
		var layer_errors := PackedStringArray()
		var ids := decode_layer(chunk_layers[key], width, height, empty_id, layer_errors)
		for i in ids.size():
			if ids[i] != empty_id and (ids[i] < 0 or ids[i] >= tiles.size()):
				layer_errors.append("palette id %d at cell (%d, %d) is outside 0..%d"
					% [ids[i], i % width, i / width, tiles.size() - 1])
				break
		for e in layer_errors:
			errors.append("layer '%s': %s" % [key, e])
		if key == "collision" and layer_errors.is_empty():
			collision_ids = ids

	if not chunk_layers.has("collision"):
		errors.append("no 'collision' layer — cannot assess walkability")
	if collision_ids.is_empty():
		return result
	var codes := _collision_codes(collision_ids, id_map, empty_id, errors)
	var walker := Walker.new(codes, width, height, opts)

	# Derive entry/exit points from entities if none were supplied.
	if entries.is_empty():
		entries = _entity_cells(chunk_data, "spawn")
	if exits.is_empty():
		exits = _entity_cells(chunk_data, "exit")
	if entries.is_empty():
		errors.append("no entry points (pass `entries` or add a 'spawn' entity)")
	if exits.is_empty():
		errors.append("no exit points (pass `exits` or add an 'exit' entity)")

	var starts: Array[Vector2i] = []
	for e in entries:
		var s := walker.start_cell(int(e[0]), int(e[1]))
		if s.x < 0:
			errors.append("entry (%d, %d) is inside solid or has no floor" % [int(e[0]), int(e[1])])
		else:
			starts.append(s)
	var links := walker.resolve_links(opts.get("links", []), errors)

	if not starts.is_empty() and not exits.is_empty():
		var seen := walker.flood(starts, links)
		var missed: Array = []
		for e in exits:
			var ex := int(e[0])
			var ey := int(e[1])
			if not walker.touches(seen, ex, ey):
				missed.append([ex, ey])
		result["reachable"] = missed.is_empty()
		result["unreachable_exits"] = missed
		if not missed.is_empty():
			errors.append("%d/%d exit(s) unreachable from entries"
				% [missed.size(), exits.size()])

	result["ok"] = errors.is_empty()
	return result


## Decode a schema layer entry ("grid" or "rle") into a flat row-major id
## array of width*height, appending any format problem to `errors`. Shared by
## WorldBuilder so both sides agree on what a well-formed payload is.
static func decode_layer(layer_data: Dictionary, width: int, height: int,
		empty_id: int, errors: PackedStringArray) -> PackedInt32Array:
	var out := PackedInt32Array()
	out.resize(width * height)
	out.fill(empty_id)
	var data: Variant = layer_data.get("data", [])
	if typeof(data) != TYPE_ARRAY:
		errors.append("'data' must be an array")
		return out
	var encoding := str(layer_data.get("encoding", ""))
	if encoding == "rle":
		if data.size() % 2 != 0:
			errors.append("rle data has odd length %d" % data.size())
		var pos := 0
		var i := 0
		while i + 1 < data.size():
			var value := int(data[i])
			var count := int(data[i + 1])
			if count < 1:
				errors.append("rle run %d has count %d" % [i / 2, count])
				return out
			if pos + count > out.size():
				errors.append("rle covers more than %d cells" % out.size())
				return out
			for n in count:
				out[pos + n] = value
			pos += count
			i += 2
		if pos != out.size():
			errors.append("rle covers %d of %d cells" % [pos, out.size()])
	elif encoding == "grid":
		if data.size() != height:
			errors.append("grid has %d rows, expected %d" % [data.size(), height])
		for y in mini(height, data.size()):
			var row: Variant = data[y]
			if typeof(row) != TYPE_ARRAY or row.size() != width:
				errors.append("grid row %d is not an array of %d ids" % [y, width])
				continue
			for x in width:
				out[y * width + x] = int(row[x])
	else:
		errors.append("unknown encoding '%s'" % encoding)
	return out


# --- collision grid ---------------------------------------------------------

## Map collision palette ids to TileMapUtils.TILE_* codes.
static func _collision_codes(ids: PackedInt32Array, id_map: Dictionary,
		empty_id: int, errors: PackedStringArray) -> PackedByteArray:
	var layers_cfg: Dictionary = id_map.get("layers", {})
	var pal_key := str(layers_cfg.get("collision", {}).get("palette", "s2_collision_tileset"))
	var col_types: Array = id_map.get("palettes", {}).get(pal_key, {}).get("collision_types", [])
	var lut := PackedByteArray()
	lut.resize(col_types.size())
	for i in col_types.size():
		var t := str(col_types[i])
		if not TYPE_CODES.has(t):
			errors.append("collision palette id %d has unknown type '%s'" % [i, t])
		lut[i] = TYPE_CODES.get(t, TileMapUtils.TILE_EMPTY)
	var out := PackedByteArray()
	out.resize(ids.size())
	for i in ids.size():
		var pid := ids[i]
		out[i] = TileMapUtils.TILE_EMPTY if pid == empty_id or pid < 0 or pid >= lut.size() else lut[pid]
	return out


## Entity positions of `etype` as [x, y] cells. Actors authored by their
## sprite's top-left (params.origin == "top_left") are moved to the cell under
## their feet centre.
static func _entity_cells(chunk_data: Dictionary, etype: String) -> Array:
	var cell := float(chunk_data.get("cell_size", 8))
	var out: Array = []
	for spec in chunk_data.get("entities", []):
		if typeof(spec) != TYPE_DICTIONARY or str(spec.get("type", "")) != etype:
			continue
		var p: Array = spec.get("position", [])
		if p.size() < 2:
			continue
		var x := float(p[0])
		var y := float(p[1])
		var params: Dictionary = spec.get("params", {})
		if str(params.get("origin", "")) == "top_left":
			var size: Array = params.get("size_px", [0, 0])
			x += float(size[0]) / cell * 0.5
			y += float(size[1]) / cell - 0.001
		out.append([floori(x), floori(y)])
	return out


# --- reachability -----------------------------------------------------------

class Walker:
	const OPEN_SKY := 1 << 20

	var w: int
	var h: int
	var codes: PackedByteArray
	var aw: int
	var ah: int
	var crouch: int
	var jump_up: int
	var jump_across: int
	var hatch: int
	## Consecutive non-solid cells from a cell upwards (open sky above row 0).
	var free_up := PackedInt32Array()
	## 1 where the agent can stand with its feet anchor on that cell.
	var stand := PackedByteArray()
	## Index of the cell a fall starting here ends on, or -1.
	var land := PackedInt32Array()

	func _init(p_codes: PackedByteArray, p_w: int, p_h: int, opts: Dictionary) -> void:
		codes = p_codes
		w = p_w
		h = p_h
		aw = maxi(1, int(opts["agent_width"]))
		ah = maxi(1, int(opts["agent_height"]))
		crouch = clampi(int(opts["crouch_height"]), 1, ah)
		jump_up = maxi(0, int(opts["jump_up"]))
		jump_across = maxi(0, int(opts["jump_across"]))
		hatch = maxi(0, int(opts["hatch_thickness"]))
		free_up.resize(w * h)
		for x in w:
			var run := OPEN_SKY
			for y in h:
				var i := y * w + x
				run = 0 if codes[i] == TileMapUtils.TILE_SOLID else run + 1
				free_up[i] = run
		stand.resize(w * h)
		for y in h:
			for x in w:
				stand[y * w + x] = 1 if _compute_standable(x, y) else 0
		land.resize(w * h)
		for x in w:
			var below := -1
			for y in range(h - 1, -1, -1):
				var i := y * w + x
				if stand[i] == 1:
					below = i
				elif not body_free(x, y, 1):
					below = -1
				land[i] = below

	func code(x: int, y: int) -> int:
		if x < 0 or x >= w or y >= h:
			return TileMapUtils.TILE_SOLID
		if y < 0:
			return TileMapUtils.TILE_EMPTY
		return codes[y * w + x]

	func is_climb(x: int, y: int) -> bool:
		var c := code(x, y)
		return c == TileMapUtils.TILE_LADDER or c == TileMapUtils.TILE_ROPE

	func body_free(x: int, y: int, height: int) -> bool:
		if y >= h or x < 0 or x + aw > w:
			return false
		if y < 0:
			return true
		for c in range(x, x + aw):
			if free_up[y * w + c] < height:
				return false
		return true

	func standable(x: int, y: int) -> bool:
		if x < 0 or x >= w or y < 0 or y >= h:
			return false
		return stand[y * w + x] == 1

	func _compute_standable(x: int, y: int) -> bool:
		if is_climb(x, y):
			return true
		if not body_free(x, y, crouch):
			return false
		for c in range(x, x + aw):
			var below := code(c, y + 1)
			if below == TileMapUtils.TILE_SOLID or below == TileMapUtils.TILE_ONEWAY:
				return true
			if below == TileMapUtils.TILE_LADDER and not is_climb(c, y):
				return true
		return false

	## Where a fall from (x, y) ends; (-1, -1) if it hits solid or the floor
	## of the chunk without landing.
	func settle(x: int, y: int) -> Vector2i:
		if x < 0 or x >= w:
			return Vector2i(-1, -1)
		var i: int = land[maxi(y, 0) * w + x] if y < h else -1
		return Vector2i(-1, -1) if i < 0 else Vector2i(i % w, i / w)

	## Feet anchor for a raw point: tries the anchors whose body covers it and
	## a couple of rows up (points are often authored inside the floor line).
	func start_cell(x: int, y: int) -> Vector2i:
		for dy: int in [0, -1, -2]:
			for ax: int in [x - aw / 2, x - aw + 1, x]:
				if body_free(ax, y + dy, 1) or is_climb(ax, y + dy):
					var s := settle(ax, y + dy)
					if s.x >= 0:
						return s
		return Vector2i(-1, -1)

	func resolve_links(raw: Array, errors: PackedStringArray) -> Dictionary:
		var out := {}
		for link in raw:
			if typeof(link) != TYPE_ARRAY or link.size() != 2:
				errors.append("link must be [[x1, y1], [x2, y2]]: %s" % str(link))
				continue
			var a := start_cell(int(link[0][0]), int(link[0][1]))
			var b := start_cell(int(link[1][0]), int(link[1][1]))
			if a.x < 0 or b.x < 0:
				errors.append("link %s has an end inside solid or without floor" % str(link))
				continue
			for pair in [[a, b], [b, a]]:
				var k: int = pair[0].y * w + pair[0].x
				if not out.has(k):
					out[k] = []
				out[k].append(pair[1])
		return out

	## Flood from all starts; returns a byte grid (1 = reachable feet anchor).
	func flood(starts: Array[Vector2i], links: Dictionary) -> PackedByteArray:
		var seen := PackedByteArray()
		seen.resize(w * h)
		var stack: Array[Vector2i] = []
		for s in starts:
			if seen[s.y * w + s.x] == 0:
				seen[s.y * w + s.x] = 1
				stack.append(s)
		while not stack.is_empty():
			var c: Vector2i = stack.pop_back()
			var next := neighbors(c.x, c.y)
			next.append_array(links.get(c.y * w + c.x, []))
			for n in next:
				var idx := n.y * w + n.x
				if seen[idx] == 0:
					seen[idx] = 1
					stack.append(n)
		return seen

	func neighbors(x: int, y: int) -> Array[Vector2i]:
		var out: Array[Vector2i] = []
		var climbing := is_climb(x, y)

		# Climb up / down on ladders & ropes, off the top of a ladder, and
		# through hatches.
		if climbing or is_climb(x, y + 1):
			if is_climb(x, y - 1) or (climbing and standable(x, y - 1)):
				out.append(Vector2i(x, y - 1))
			if is_climb(x, y + 1):
				out.append(Vector2i(x, y + 1))
		if climbing:
			var up_exit := through_hatch(x, y, -1)
			if up_exit.x >= 0:
				out.append(up_exit)
		elif standable(x, y):
			var down_exit := through_hatch(x, y, 1)
			if down_exit.x >= 0:
				out.append(down_exit)

		# Walk / crawl one cell, or step off a ledge and fall.
		for dx: int in [-1, 1]:
			var nx := x + dx
			if standable(nx, y):
				out.append(Vector2i(nx, y))
			elif body_free(nx, y, crouch):
				var landed := settle(nx, y)
				if landed.x >= 0:
					out.append(landed)

		# Jump: rise `up` cells, drift sideways at that height, fall.
		if climbing or not body_free(x, y, ah):
			return out
		for up in range(0, jump_up + 1):
			var ty := y - up
			if not body_free(x, ty, ah):
				break
			if up > 0 and standable(x, ty):
				out.append(Vector2i(x, ty))
			for dir: int in [-1, 1]:
				for dx in range(1, jump_across + 1):
					var nx := x + dir * dx
					if not body_free(nx, ty, ah):
						break
					var landed := settle(nx, ty)
					if landed.x >= 0:
						out.append(landed)
		return out

	## Cell past a hatch slab next to (x, y) in direction `dir` (-1 up, 1
	## down): up lands on rungs or on top of the slab, down only on rungs.
	func through_hatch(x: int, y: int, dir: int) -> Vector2i:
		var yy := y + dir
		var thickness := 0
		while code(x, yy) == TileMapUtils.TILE_SOLID:
			thickness += 1
			if thickness > hatch or yy < 0 or yy >= h:
				return Vector2i(-1, -1)
			yy += dir
		if thickness == 0 or yy < 0 or yy >= h:
			return Vector2i(-1, -1)
		if is_climb(x, yy) or (dir < 0 and standable(x, yy)):
			return Vector2i(x, yy)
		return Vector2i(-1, -1)

	## True if a reachable body box covers point (px, py): some reachable feet
	## anchor lies at most one body height below it with no solid in between.
	func touches(seen: PackedByteArray, px: int, py: int) -> bool:
		if px < 0 or px >= w or py >= h:
			return false
		for dy in ah:
			var y := py + dy
			if y >= h or code(px, y) == TileMapUtils.TILE_SOLID:
				break
			if y < 0:
				continue
			for x in range(maxi(px - aw + 1, 0), px + 1):
				if seen[y * w + x] == 1:
					return true
		return false
