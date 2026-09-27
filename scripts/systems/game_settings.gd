extends Node
## Autoload: player options, applied the moment they change and restored on
## start. Shares user://settings.cfg with TiltSteer, which still owns the
## `controls/tilt_steer` key; every save reloads the file first so neither
## side drops the other's keys.

signal changed

const AUDIO_SECTION := "audio"
const CONTROLS_SECTION := "controls"
const DEFAULTS := {
	"sfx_volume": 1.0,
	"music_volume": 0.7,
	"tilt_sensitivity": 1.0,
	"pad_scale": 1.0,
	"pad_opacity": 1.0,
}
const MIN_PAD_SCALE := 0.7
const MAX_PAD_SCALE := 1.5
const MIN_PAD_OPACITY := 0.3

var config_path: String = TiltSteer.CONFIG_PATH

var sfx_volume: float = DEFAULTS["sfx_volume"]:
	set(value):
		sfx_volume = clampf(value, 0.0, 1.0)
		AudioManager.set_sfx_volume(sfx_volume)
		_on_value_changed()

var music_volume: float = DEFAULTS["music_volume"]:
	set(value):
		music_volume = clampf(value, 0.0, 1.0)
		AudioManager.set_music_volume(music_volume)
		_on_value_changed()

var tilt_sensitivity: float = DEFAULTS["tilt_sensitivity"]:
	set(value):
		TiltSteer.sensitivity = value
		tilt_sensitivity = TiltSteer.sensitivity
		_on_value_changed()

var pad_scale: float = DEFAULTS["pad_scale"]:
	set(value):
		pad_scale = clampf(value, MIN_PAD_SCALE, MAX_PAD_SCALE)
		_on_value_changed()

var pad_opacity: float = DEFAULTS["pad_opacity"]:
	set(value):
		pad_opacity = clampf(value, MIN_PAD_OPACITY, 1.0)
		_on_value_changed()

var tilt_enabled: bool:
	get:
		return TiltSteer.enabled
	set(value):
		TiltSteer.enabled = value

var _loading: bool = false


func _ready() -> void:
	TiltSteer.enabled_changed.connect(_on_tilt_enabled_changed)
	load_settings()


## Points both this autoload and TiltSteer at another file (tests use a temp one).
func use_config_path(path: String) -> void:
	config_path = path
	TiltSteer.config_path = path


func load_settings() -> void:
	var cfg := ConfigFile.new()
	var found := cfg.load(config_path) == OK
	_loading = true
	sfx_volume = float(cfg.get_value(AUDIO_SECTION, "sfx_volume", DEFAULTS["sfx_volume"]))
	music_volume = float(cfg.get_value(AUDIO_SECTION, "music_volume", DEFAULTS["music_volume"]))
	tilt_sensitivity = float(
		cfg.get_value(CONTROLS_SECTION, "tilt_sensitivity", DEFAULTS["tilt_sensitivity"])
	)
	pad_scale = float(cfg.get_value(CONTROLS_SECTION, "pad_scale", DEFAULTS["pad_scale"]))
	pad_opacity = float(cfg.get_value(CONTROLS_SECTION, "pad_opacity", DEFAULTS["pad_opacity"]))
	if found:
		TiltSteer.enabled = bool(cfg.get_value(CONTROLS_SECTION, TiltSteer.CONFIG_KEY, false))
	_loading = false
	changed.emit()


func save_settings() -> void:
	var cfg := ConfigFile.new()
	cfg.load(config_path)
	cfg.set_value(AUDIO_SECTION, "sfx_volume", sfx_volume)
	cfg.set_value(AUDIO_SECTION, "music_volume", music_volume)
	cfg.set_value(CONTROLS_SECTION, "tilt_sensitivity", tilt_sensitivity)
	cfg.set_value(CONTROLS_SECTION, "pad_scale", pad_scale)
	cfg.set_value(CONTROLS_SECTION, "pad_opacity", pad_opacity)
	cfg.save(config_path)


func _on_value_changed() -> void:
	# Not ready yet means the player's file has not been read: saving now
	# would write defaults over it.
	if _loading or not is_node_ready():
		return
	save_settings()
	changed.emit()


func _on_tilt_enabled_changed(_is_on: bool) -> void:
	if not _loading:
		changed.emit()
