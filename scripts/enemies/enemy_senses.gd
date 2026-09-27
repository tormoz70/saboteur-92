class_name EnemySenses
extends RefCounted

## Line of sight and footing probes shared by guards and panthers.
##
## Sight follows the map rule for the collision layer: solid cells and lift
## shaft rock hide Nina, one-way platforms are floors you look past, and
## ladders and ropes have no physics shape at all.

const SIGHT_MASK := CollisionLayers.LAYER_WORLD | CollisionLayers.LAYER_LIFT_SHAFT
# A ray re-cast past every one-way cell it meets; a long one-way run along
# the ray gives up rather than looping.
const MAX_SIGHT_HOPS := 24
# Sprite px the wall probe lifts the body first, so a resting contact with
# the floor below does not read as a wall.
const WALL_PROBE_LIFT := 2.0


## True if the segment from `from` to `to` crosses no sight-blocking shape.
static func has_line_of_sight(
	space: PhysicsDirectSpaceState2D, from: Vector2, to: Vector2, exclude: Array[RID] = []
) -> bool:
	var dir := (to - from).normalized()
	var query := PhysicsRayQueryParameters2D.create(from, to, SIGHT_MASK, exclude)
	for _i in MAX_SIGHT_HOPS:
		var hit := space.intersect_ray(query)
		if hit.is_empty():
			return true
		if blocks_sight(hit):
			return false
		query.from = (hit.position as Vector2) + dir
		if (to - query.from).dot(dir) <= 0.0:
			return true
	return false


## Whether a ray hit landed on something you cannot see through.
static func blocks_sight(hit: Dictionary) -> bool:
	var layer := hit.collider as TileMapLayer
	if layer:
		var inside: Vector2 = (hit.position as Vector2) - (hit.normal as Vector2) * 0.5
		var cell := layer.local_to_map(layer.to_local(inside))
		return TileMapUtils.get_collision_type(layer, cell) != "oneway"
	var body := hit.collider as CollisionObject2D
	if body:
		var owner_id := body.shape_find_owner(int(hit.shape))
		return not body.is_shape_owner_one_way_collision_enabled(owner_id)
	return true


## Points on `target` worth looking at: its body centre and its head.
static func sight_points(target: Node2D) -> Array[Vector2]:
	var col := target.get_node_or_null("CollisionShape2D") as CollisionShape2D
	if col == null or not col.shape is RectangleShape2D:
		return [target.global_position]
	var half_h := (col.shape as RectangleShape2D).size.y * 0.5 * col.global_scale.y
	var centre := col.global_position
	return [centre, centre - Vector2(0.0, half_h * 0.7)]


## True if any sight point of `target` is visible from `eye`.
static func can_see(viewer: CollisionObject2D, eye: Vector2, target: Node2D) -> bool:
	var space := viewer.get_world_2d().direct_space_state
	for point in sight_points(target):
		if has_line_of_sight(space, eye, point, [viewer.get_rid()]):
			return true
	return false


## True if stepping `dir` would put the whole body past the floor's edge.
## `body_width` and `depth` are sprite px; the body's scale is applied here.
## A lift cabin counts as an edge: it would carry the enemy off its floor.
static func ledge_ahead(
	body: CharacterBody2D, dir: int, body_width: float, depth: float
) -> bool:
	if not body.is_on_floor():
		return false
	var s := body.global_scale
	var ahead := body.global_transform.translated(Vector2(float(dir) * body_width * s.x, 0.0))
	var hit := KinematicCollision2D.new()
	if not body.test_move(ahead, Vector2(0.0, depth * s.y), hit):
		return true
	var under := hit.get_collider() as Node
	return under != null and under.is_in_group("lifts")


## True if a wall stands within `reach` sprite px in direction `dir`.
static func wall_ahead(body: CharacterBody2D, dir: int, reach: float) -> bool:
	if body.is_on_wall() and body.get_wall_normal().x * float(dir) < -0.5:
		return true
	var s := body.global_scale
	var from := body.global_transform
	var lift := Vector2(0.0, -WALL_PROBE_LIFT * s.y)
	if not body.test_move(from, lift):
		from = from.translated(lift)
	return body.test_move(from, Vector2(float(dir) * reach * s.x, 0.0))
