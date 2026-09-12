class_name WorldLayers
extends Object

## Authoring layer ids (z-order). Not physics collision layers.
## 0 sky, 1 earth, 2 structure, 3 wallpaper, 4 interior,
## 5 machines, 6 artifacts, 7 actors, 8 fg.

const SKY := 0
const EARTH := 1
const STRUCTURE := 2
const WALLPAPER := 3
const INTERIOR := 4
const MACHINES := 5
const ARTIFACTS := 6
const ACTORS := 7
const FG := 8

const Z_SKY := -30
const Z_EARTH := -20
const Z_STRUCTURE := -10
const Z_WALLPAPER := -5
const Z_INTERIOR := 0
const Z_INTERIOR_PROPS := 1
const Z_ARTIFACTS := 7
const Z_MACHINES := 6
const Z_ACTORS := 8
const Z_FG := 12
const Z_COLLISION := 20

const TILE_LAYER_NAMES: Array[String] = [
	"sky", "earth", "structure", "wallpaper", "interior", "fg"
]

const LAYER_ORDER: Array[String] = [
	"sky",
	"earth",
	"structure",
	"wallpaper",
	"interior",
	"artifacts",
	"machines",
	"actors",
	"fg",
]

const LAYER_Z: Dictionary = {
	"sky": Z_SKY,
	"earth": Z_EARTH,
	"structure": Z_STRUCTURE,
	"wallpaper": Z_WALLPAPER,
	"interior": Z_INTERIOR,
	"artifacts": Z_ARTIFACTS,
	"machines": Z_MACHINES,
	"actors": Z_ACTORS,
	"fg": Z_FG,
}
