class_name CollisionLayers
extends Object

# Bit values of project.godot layer_1..layer_6
# (player, enemy, world, items, triggers, lift_shaft).
const LAYER_PLAYER := 1
const LAYER_ENEMY := 2
const LAYER_WORLD := 4
const LAYER_ITEMS := 8
const LAYER_TRIGGERS := 16
# Rock the lift cabin travels through: solid for everyone except a lift rider.
const LAYER_LIFT_SHAFT := 32
