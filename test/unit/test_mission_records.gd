extends GutTest
## Best time / best score records, written to a temp file.

const TEMP_PATH := "user://test_records_tmp.cfg"


func before_each() -> void:
	_remove_temp()


func after_each() -> void:
	_remove_temp()


func test_no_file_means_no_record() -> void:
	var best := MissionRecords.load_best(TEMP_PATH)
	assert_eq(best["time"], 0.0)
	assert_eq(best["score"], 0)
	assert_eq(best["wins"], 0)


func test_first_win_sets_both_records() -> void:
	var best := MissionRecords.submit(95.5, 650, false, TEMP_PATH)
	assert_true(best["new_time"])
	assert_true(best["new_score"])
	assert_almost_eq(float(best["time"]), 95.5, 0.001)
	assert_eq(int(best["score"]), 650)
	assert_eq(int(best["wins"]), 1)


func test_worse_run_does_not_overwrite_the_best() -> void:
	MissionRecords.submit(80.0, 900, false, TEMP_PATH)
	var best := MissionRecords.submit(120.0, 400, true, TEMP_PATH)
	assert_false(best["new_time"])
	assert_false(best["new_score"])
	assert_almost_eq(float(best["time"]), 80.0, 0.001)
	assert_eq(int(best["score"]), 900)
	assert_false(best["time_alarmed"], "alarm flag belongs to the best-time run")
	assert_eq(int(best["wins"]), 2)


func test_records_improve_independently() -> void:
	MissionRecords.submit(80.0, 900, false, TEMP_PATH)
	var faster := MissionRecords.submit(70.0, 500, true, TEMP_PATH)
	assert_true(faster["new_time"])
	assert_false(faster["new_score"])
	assert_almost_eq(float(faster["time"]), 70.0, 0.001)
	assert_true(faster["time_alarmed"])
	assert_eq(int(faster["score"]), 900)
	var richer := MissionRecords.submit(99.0, 1200, false, TEMP_PATH)
	assert_false(richer["new_time"])
	assert_true(richer["new_score"])
	assert_eq(int(richer["score"]), 1200)


func test_records_survive_a_reload() -> void:
	MissionRecords.submit(61.2, 650, false, TEMP_PATH)
	var best := MissionRecords.load_best(TEMP_PATH)
	assert_almost_eq(float(best["time"]), 61.2, 0.001)
	assert_eq(int(best["score"]), 650)


func test_format_time() -> void:
	assert_eq(MissionRecords.format_time(0.0), "--:--.-")
	assert_eq(MissionRecords.format_time(5.25), "00:05.2")
	assert_eq(MissionRecords.format_time(59.99), "00:59.9")
	assert_eq(MissionRecords.format_time(125.4), "02:05.4")


func _remove_temp() -> void:
	if FileAccess.file_exists(TEMP_PATH):
		DirAccess.remove_absolute(TEMP_PATH)
