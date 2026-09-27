class_name LiftPanel
extends Area2D
## Lift call console beside a station: a punch or kick calls the cabin there.

var lift: Lift = null
var to_top: bool = true


func _ready() -> void:
	collision_layer = CollisionLayers.LAYER_ITEMS
	collision_mask = 0
	monitoring = false


func on_punched() -> bool:
	return lift != null and lift.summon(to_top)
