class_name WorldLayers
extends Object

## Authoring layer ids (z-order). Not physics collision layers.
## 0 sky, 1 earth, 2 structure, 3 interior, 4 artifacts, 5 machines, 6 actors, 7 fg

const SKY := 0
const EARTH := 1
const STRUCTURE := 2
const INTERIOR := 3
const ARTIFACTS := 4
const MACHINES := 5
const ACTORS := 6
const FG := 7
## Wallpaper merged into interior (room paper is an interior fill object).
const WALLPAPER := INTERIOR

const Z_SKY := -30
const Z_EARTH := -20
const Z_STRUCTURE := -10
const Z_INTERIOR := 0
const Z_WALLPAPER := -15
const Z_INTERIOR_PROPS := 1
const Z_ARTIFACTS := 7
const Z_MACHINES := 6
const Z_ACTORS := 8
const Z_FG := 12

const LAYER_ORDER: Array[String] = [
	"sky", "earth", "structure", "interior", "artifacts", "machines", "actors", "fg"
]

const LAYER_Z: Dictionary = {
	"sky": Z_SKY,
	"earth": Z_EARTH,
	"structure": Z_STRUCTURE,
	"interior": Z_INTERIOR,
	"artifacts": Z_ARTIFACTS,
	"machines": Z_MACHINES,
	"actors": Z_ACTORS,
	"fg": Z_FG,
}
