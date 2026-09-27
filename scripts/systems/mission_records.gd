class_name MissionRecords
extends RefCounted
## Best escape time and best score, kept between runs in a ConfigFile.

const RECORDS_PATH := "user://records.cfg"
const SECTION := "lab_mission"


static func load_best(path: String = RECORDS_PATH) -> Dictionary:
	var cfg := ConfigFile.new()
	cfg.load(path)
	return {
		"time": float(cfg.get_value(SECTION, "best_time", 0.0)),
		"time_alarmed": bool(cfg.get_value(SECTION, "best_time_alarmed", false)),
		"score": int(cfg.get_value(SECTION, "best_score", 0)),
		"wins": int(cfg.get_value(SECTION, "wins", 0)),
	}


## Stores a won run. Returns the best values after it plus which of them it set.
static func submit(
	time_sec: float, score: int, alarmed: bool, path: String = RECORDS_PATH
) -> Dictionary:
	var cfg := ConfigFile.new()
	cfg.load(path)
	var best_time := float(cfg.get_value(SECTION, "best_time", 0.0))
	var best_score := int(cfg.get_value(SECTION, "best_score", 0))
	var new_time := time_sec > 0.0 and (best_time <= 0.0 or time_sec < best_time)
	var new_score := score > best_score
	if new_time:
		cfg.set_value(SECTION, "best_time", time_sec)
		cfg.set_value(SECTION, "best_time_alarmed", alarmed)
	if new_score:
		cfg.set_value(SECTION, "best_score", score)
	cfg.set_value(SECTION, "wins", int(cfg.get_value(SECTION, "wins", 0)) + 1)
	cfg.save(path)
	var best := load_best(path)
	best["new_time"] = new_time
	best["new_score"] = new_score
	return best


static func format_time(seconds: float) -> String:
	if seconds <= 0.0:
		return "--:--.-"
	var tenths := floori(seconds * 10.0)
	var minutes := floori(tenths / 600.0)
	var rest := tenths - minutes * 600
	return "%02d:%02d.%d" % [minutes, floori(rest / 10.0), rest % 10]
