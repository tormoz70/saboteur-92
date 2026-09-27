extends RefCounted
## Small collision worlds for the enemy tests, built from the real collision
## TileSet at the level's x2 scale, so sight rays and footing probes meet the
## same solid and one-way tiles they meet in the game.

const COLLISION_TILESET := preload("res://assets/tilesets/s2_collision_tileset.tres")
const SCALE := 2.0
## World px per collision cell at SCALE.
const CELL := 16.0
const SOLID := 1
const LADDER := 2
const ONEWAY := 3


static func make_layer() -> TileMapLayer:
	var layer := TileMapLayer.new()
	layer.name = "CollisionLayer"
	layer.tile_set = COLLISION_TILESET
	layer.scale = Vector2(SCALE, SCALE)
	return layer


## Fill the inclusive cell rectangle with one collision kind.
static func fill(layer: TileMapLayer, x0: int, y0: int, x1: int, y1: int, kind: int) -> void:
	for y in range(y0, y1 + 1):
		for x in range(x0, x1 + 1):
			layer.set_cell(Vector2i(x, y), 0, Vector2i(kind, 0))


## World y of the top of cell row `row`.
static func row_top(row: int) -> float:
	return float(row) * CELL


## Origin y that puts a scaled actor's feet (sprite px below its origin) on
## the floor whose top is `floor_top`.
static func origin_on_floor(floor_top: float, feet: float) -> float:
	return floor_top - feet * SCALE
