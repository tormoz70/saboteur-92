extends GutTest
## ChunkValidator: rope is a horizontal crossing, not a vertical climb.


func test_rope_crosses_a_gap_between_platforms() -> void:
	# Two solid pads with a rope span between them. Spawn on the left pad,
	# exit on the right — only reachable by running the rope.
	# Feet stand on the row ABOVE the support (solid / rope), same as floors.
	var w := 24
	var h := 12
	var codes := PackedByteArray()
	codes.resize(w * h)
	codes.fill(TileMapUtils.TILE_EMPTY)
	for x in range(1, 5):
		codes[8 * w + x] = TileMapUtils.TILE_SOLID
	for x in range(5, 18):
		codes[8 * w + x] = TileMapUtils.TILE_ROPE
	for x in range(18, 22):
		codes[8 * w + x] = TileMapUtils.TILE_SOLID
	var walker := ChunkValidator.Walker.new(codes, w, h, ChunkValidator.DEFAULT_OPTIONS)
	assert_true(walker.is_rope(10, 8), "rope cells are recognised")
	assert_false(walker.is_climb(10, 8), "rope is not a vertical climb")
	assert_true(walker.standable(10, 7), "feet above rope are standable")
	var start := walker.start_cell(2, 7)
	assert_gt(start.x, -1, "left pad has a start")
	var seen := walker.flood([start], {})
	assert_eq(seen[7 * w + 10], 1, "rope mid-span is reachable")
	assert_true(walker.touches(seen, 19, 7), "right pad is reachable via rope")


func test_rope_without_crossing_does_not_bridge_a_chasm() -> void:
	var w := 24
	var h := 12
	var codes := PackedByteArray()
	codes.resize(w * h)
	codes.fill(TileMapUtils.TILE_EMPTY)
	for x in range(1, 5):
		codes[8 * w + x] = TileMapUtils.TILE_SOLID
	for x in range(18, 22):
		codes[8 * w + x] = TileMapUtils.TILE_SOLID
	var walker := ChunkValidator.Walker.new(codes, w, h, ChunkValidator.DEFAULT_OPTIONS)
	var start := walker.start_cell(2, 7)
	var seen := walker.flood([start], {})
	assert_false(walker.touches(seen, 19, 7), "gap without rope blocks the crossing")
