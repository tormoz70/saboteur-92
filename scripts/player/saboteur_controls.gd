class_name SaboteurControls
extends RefCounted
## Static Saboteur II inlay table. Do not instantiate.
## https://worldofspectrum.net/pub/sinclair/games-info/s/SaboteurII.txt
##
## UP if still = kick. MOVE+UP = running jump. FIRE if still = punch.
## MOVE+FIRE = flying kick. DOWN if still = duck. jump is an UP synonym.
## FIRE in the air does nothing; the flying kick starts on the ground.

enum GroundAction { NONE, STAND_KICK, RUNNING_JUMP, FLYING_KICK, PUNCH }


static func wants_up() -> bool:
	return Input.is_action_pressed("move_up") or Input.is_action_pressed("jump")


static func just_up() -> bool:
	return Input.is_action_just_pressed("move_up") or Input.is_action_just_pressed("jump")


static func wants_down() -> bool:
	return Input.is_action_pressed("move_down")


static func climb_axis() -> float:
	var up := 1.0 if wants_up() else 0.0
	var down := 1.0 if wants_down() else 0.0
	# Same sign as Input.get_axis("move_up", "move_down"): up is negative.
	return down - up


static func resolve_ground(
	moving: bool,
	up_tap: bool,
	punch_tap: bool,
	can_climb: bool,
	lift_takes_up: bool
) -> GroundAction:
	if lift_takes_up and up_tap:
		return GroundAction.NONE
	if moving and up_tap:
		return GroundAction.RUNNING_JUMP
	if can_climb and up_tap:
		return GroundAction.NONE
	if up_tap:
		return GroundAction.STAND_KICK
	if punch_tap and moving:
		return GroundAction.FLYING_KICK
	if punch_tap:
		return GroundAction.PUNCH
	return GroundAction.NONE


static func should_crouch(moving: bool, down_held: bool, lift_takes_down: bool) -> bool:
	return down_held and not moving and not lift_takes_down
