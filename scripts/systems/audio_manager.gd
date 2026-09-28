extends Node
## Autoload: Master / SFX / Music buses, SFX pool, looping theme.
## Safe under the Dummy audio driver (headless GUT / --demo).

const SFX_DIR := "res://assets/audio/sfx/"
const MUSIC_DIR := "res://assets/audio/music/"
const POOL_SIZE := 8
const FUSE_TICK_SEC := 1.0

const SFX_NAMES := [
	"step",
	"punch",
	"hit",
	"somersault",
	"land",
	"ladder",
	"lift_start",
	"lift_stop",
	"pickup",
	"alarm",
	"spotted",
	"fuse_tick",
	"death",
	"win",
	"rope_mount",
	"rope_fall",
]

var play_counts: Dictionary = {}
var last_sfx: String = ""

var _streams: Dictionary = {}
var _pool: Array[AudioStreamPlayer] = []
var _music: AudioStreamPlayer
var _theme: AudioStream
var _theme_fast: AudioStream
var _fuse_acc: float = 0.0
var _urgent: bool = false
var _pool_size: int = POOL_SIZE
var _paused: bool = false


func _ready() -> void:
	_load_streams()
	_build_pool()
	_music = AudioStreamPlayer.new()
	_music.name = "MusicPlayer"
	_music.bus = &"Music"
	add_child(_music)
	EventBus.item_collected.connect(_on_item_collected)
	EventBus.alarm_raised.connect(_on_alarm_raised)
	EventBus.player_died.connect(_on_player_died)
	EventBus.mission_complete.connect(_on_mission_complete)
	EventBus.bomb_planted.connect(_on_bomb_planted)
	play_music(false)


func _exit_tree() -> void:
	for p in _pool + [_music]:
		if is_instance_valid(p):
			p.stop()
			p.stream = null
	_streams.clear()
	_theme = null
	_theme_fast = null


func _process(delta: float) -> void:
	var playing := GameManager.state == GameManager.GameState.PLAYING
	if not GameManager.bomb_planted or not playing:
		_fuse_acc = 0.0
		if _urgent and playing and not GameManager.bomb_planted:
			set_music_urgent(false)
		return
	_fuse_acc += delta
	if _fuse_acc < FUSE_TICK_SEC:
		return
	_fuse_acc = 0.0
	play_sfx("fuse_tick")


func play_sfx(sfx_name: String) -> void:
	if _paused or not _streams.has(sfx_name):
		return
	var player := _acquire()
	if player == null:
		return
	player.stream = _streams[sfx_name]
	player.play()
	_note(sfx_name)


func play_music(urgent: bool = false) -> void:
	_urgent = urgent
	var stream: AudioStream = _theme_fast if urgent else _theme
	if stream == null:
		return
	if _music.stream == stream and _music.playing:
		return
	_music.stream = stream
	_music.play()


func stop_music() -> void:
	_music.stop()
	_urgent = false


## Game pause: holds the theme where it is and drops new effects. Kept as a
## flag because stream_paused does not stick on a player with no playback.
func set_paused(paused: bool) -> void:
	_paused = paused
	_music.stream_paused = paused
	for p in _pool:
		p.stream_paused = paused


func is_paused() -> bool:
	return _paused


func set_music_urgent(urgent: bool) -> void:
	if _urgent == urgent:
		return
	play_music(urgent)


func set_master_volume(linear: float) -> void:
	_set_bus_volume(&"Master", linear)


func set_sfx_volume(linear: float) -> void:
	_set_bus_volume(&"SFX", linear)


func set_music_volume(linear: float) -> void:
	_set_bus_volume(&"Music", linear)


func get_pool_size() -> int:
	return _pool.size()


func reset_play_counts() -> void:
	play_counts.clear()
	last_sfx = ""


func _on_item_collected(_item_type: String) -> void:
	play_sfx("pickup")


func _on_alarm_raised() -> void:
	play_sfx("alarm")


func _on_player_died() -> void:
	play_sfx("death")
	if GameManager.state == GameManager.GameState.LOST:
		stop_music()
	else:
		set_music_urgent(false)


func _on_mission_complete() -> void:
	play_sfx("win")
	stop_music()


func _on_bomb_planted() -> void:
	_fuse_acc = 0.0
	set_music_urgent(true)


func _load_streams() -> void:
	_streams.clear()
	for sfx_name in SFX_NAMES:
		var path: String = SFX_DIR + sfx_name + ".wav"
		if not ResourceLoader.exists(path):
			continue
		var stream := load(path) as AudioStream
		if stream != null:
			_streams[sfx_name] = stream
	_theme = _load_music("theme")
	_theme_fast = _load_music("theme_fast")


func _load_music(track: String) -> AudioStream:
	var path: String = MUSIC_DIR + track + ".wav"
	if not ResourceLoader.exists(path):
		return null
	var stream := load(path) as AudioStream
	if stream is AudioStreamWAV:
		var wav := stream as AudioStreamWAV
		wav.loop_mode = AudioStreamWAV.LOOP_FORWARD
	return stream


func _build_pool() -> void:
	for child in _pool:
		if is_instance_valid(child):
			child.queue_free()
	_pool.clear()
	for i in _pool_size:
		var p := AudioStreamPlayer.new()
		p.name = "Sfx_%d" % i
		p.bus = &"SFX"
		add_child(p)
		_pool.append(p)


func _acquire() -> AudioStreamPlayer:
	for p in _pool:
		if not p.playing:
			return p
	# Dummy driver (headless) may leave every player marked playing; reuse.
	return _pool[0] if not _pool.is_empty() else null


func _note(sfx_name: String) -> void:
	last_sfx = sfx_name
	play_counts[sfx_name] = int(play_counts.get(sfx_name, 0)) + 1


func _set_bus_volume(bus_name: StringName, linear: float) -> void:
	var idx := AudioServer.get_bus_index(bus_name)
	if idx < 0:
		return
	var v := clampf(linear, 0.0, 1.0)
	AudioServer.set_bus_volume_db(idx, linear_to_db(v) if v > 0.0001 else -80.0)
