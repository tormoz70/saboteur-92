extends Node

signal enemy_killed(enemy: Node)
signal item_collected(item_type: String)
signal bomb_planted
signal player_died
signal mission_complete
signal score_changed(new_score: int)
signal energy_changed(current: int, max_energy: int)
signal marker_seen(label: String)
signal alarm_raised
