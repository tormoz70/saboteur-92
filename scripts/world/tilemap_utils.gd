class_name TileMapUtils
extends Object

## RLE tile grids and greedy collision merge. Mirrors
## tools/saboteur_rip/collision_tiles.py / greedy_rects.

const TILE_EMPTY := 0
const TILE_SOLID := 1
const TILE_LADDER := 2
const TILE_ONEWAY := 3
const CELL := 8


static func rle_decode(runs: Array) -> PackedInt32Array:
	var out := PackedInt32Array()
	var i := 0
	while i + 1 < runs.size():
		var value := int(runs[i])
		var count := int(runs[i + 1])
		var start := out.size()
		out.resize(start + count)
		for n in count:
			out[start + n] = value
		i += 2
	return out


static func rle_encode(ids: PackedInt32Array) -> Array:
	var out: Array = []
	if ids.is_empty():
		return out
	var prev := ids[0]
	var count := 1
	for i in range(1, ids.size()):
		if ids[i] == prev:
			count += 1
		else:
			out.append(prev)
			out.append(count)
			prev = ids[i]
			count = 1
	out.append(prev)
	out.append(count)
	return out


static func atlas_coords(tile_id: int, atlas_cols: int) -> Vector2i:
	if atlas_cols <= 0:
		return Vector2i.ZERO
	return Vector2i(tile_id % atlas_cols, int(tile_id / atlas_cols))


static func fill_from_rle(layer: TileMapLayer, spec: Dictionary) -> void:
	var runs: Array = spec.get("rle", [])
	var ids := rle_decode(runs)
	var atlas: Array = spec.get("atlas_tiles", [1, 1])
	var atlas_cols := int(atlas[0]) if atlas.size() > 0 else 1
	var empty_id := int(spec.get("empty", TILE_EMPTY))
	var has_empty := spec.has("empty")
	var grid: Array = spec.get("grid", [])
	var cw := int(grid[0]) if grid.size() > 0 else 0
	if cw <= 0:
		cw = maxi(ids.size(), 1)
	var packed := PackedByteArray()
	var used := 0
	for i in ids.size():
		if has_empty and ids[i] == empty_id:
			continue
		used += 1
	packed.resize(2 + used * 12)
	packed.encode_u16(0, 0)
	used = 0
	for i in ids.size():
		var tid: int = ids[i]
		if has_empty and tid == empty_id:
			continue
		var cell := Vector2i(i % cw, int(i / cw))
		var atlas_xy := atlas_coords(tid, atlas_cols)
		var base := 2 + used * 12
		packed.encode_s16(base, cell.x)
		packed.encode_s16(base + 2, cell.y)
		packed.encode_u16(base + 4, 0)
		packed.encode_u16(base + 6, atlas_xy.x)
		packed.encode_u16(base + 8, atlas_xy.y)
		packed.encode_u16(base + 10, 0)
		used += 1
	layer.tile_map_data = packed


static func get_collision_type(tilemap: TileMapLayer, cell: Vector2i) -> String:
	var tile_data := tilemap.get_cell_tile_data(cell)
	if tile_data == null:
		return "empty"
	var value: Variant = tile_data.get_custom_data("collision_type")
	if typeof(value) == TYPE_STRING and str(value) != "":
		return str(value)
	var atlas := tilemap.get_cell_atlas_coords(cell)
	match atlas.x:
		TILE_SOLID:
			return "solid"
		TILE_LADDER:
			return "ladder"
		TILE_ONEWAY:
			return "oneway"
		_:
			return "empty"


static func _row_set(grid: Array, y: int, x: int, value: int) -> void:
	var row: PackedInt32Array = grid[y]
	row[x] = value
	grid[y] = row


static func apply_hatches(solid: Array, ladder: Array) -> void:
	var ch := solid.size()
	if ch == 0:
		return
	var lids: Array[Vector2i] = []
	for y in ch:
		var srow: PackedInt32Array = solid[y]
		var lrow: PackedInt32Array = ladder[y]
		var cw := srow.size()
		for x in cw:
			if lrow[x] == 0:
				continue
			for dx in PackedInt32Array([-1, 1]):
				var nx: int = x + dx
				if nx < 0 or nx >= cw:
					continue
				if srow[nx] != 0 and lrow[nx] == 0:
					lids.append(Vector2i(x, y))
					break
	for cell in lids:
		_row_set(solid, cell.y, cell.x, 1)


static func ids_to_masks(
	ids: PackedInt32Array, cw: int, ch: int, climb_ids: PackedInt32Array
) -> Dictionary:
	var solid: Array = []
	var climb: Array = []
	var has_climb := climb_ids.size() == ids.size() and not climb_ids.is_empty()
	for y in ch:
		var srow := PackedInt32Array()
		var lrow := PackedInt32Array()
		srow.resize(cw)
		lrow.resize(cw)
		for x in cw:
			var i := y * cw + x
			var tid := 0
			if i < ids.size():
				tid = ids[i]
			if tid == TILE_SOLID or tid == TILE_ONEWAY:
				srow[x] = 1
			if has_climb:
				if i < climb_ids.size() and climb_ids[i] != 0:
					lrow[x] = 1
			elif tid == TILE_LADDER:
				lrow[x] = 1
		solid.append(srow)
		climb.append(lrow)
	return {"solid": solid, "climb": climb}


static func greedy_merge_rects(grid: Array, cell: int = CELL) -> Array:
	var ch := grid.size()
	if ch == 0:
		return []
	var cw: int = (grid[0] as PackedInt32Array).size()
	var seen: Array = []
	for _y in ch:
		var row := PackedInt32Array()
		row.resize(cw)
		seen.append(row)
	var rects: Array = []
	for y in ch:
		var grow: PackedInt32Array = grid[y]
		for x in cw:
			if grow[x] == 0 or (seen[y] as PackedInt32Array)[x] != 0:
				continue
			var x1 := x
			while (
				x1 < cw
				and (grid[y] as PackedInt32Array)[x1] != 0
				and (seen[y] as PackedInt32Array)[x1] == 0
			):
				x1 += 1
			var y1 := y + 1
			var can_grow := true
			while y1 < ch and can_grow:
				var nrow: PackedInt32Array = grid[y1]
				var srow: PackedInt32Array = seen[y1]
				for xx in range(x, x1):
					if nrow[xx] == 0 or srow[xx] != 0:
						can_grow = false
						break
				if can_grow:
					y1 += 1
			for yy in range(y, y1):
				for xx in range(x, x1):
					_row_set(seen, yy, xx, 1)
			rects.append([x * cell, y * cell, (x1 - x) * cell, (y1 - y) * cell])
	return rects


static func ladder_rects(climb: Array, cell: int = CELL) -> Array:
	var rects: Array = []
	for rect in greedy_merge_rects(climb, cell):
		if int(rect[3]) < 24:
			continue
		rects.append([int(rect[0]) - 4, rect[1], int(rect[2]) + 8, rect[3]])
	return rects
