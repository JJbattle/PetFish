extends Node
## Feature engine for the pet: drinking water, sitting too long, alarms and
## memos.  It owns the persisted settings and emits `notice` when something
## should be shown in the speech bubble.
##
## Reminders only run while the pet is running - there is no background
## service - which is fine because the pet is meant to be always up.

signal notice(kind: String, text: String)
signal water_logged(ml: int, total_ml: int, goal_ml: int)
signal changed

const DATA_PATH := "I:/PetFish/data/pet_data.json"
const TICK := 1.0

var _data: Dictionary = {}
var _tick := 0.0
## Overridable so the test harness can use a throwaway profile.
var data_path := DATA_PATH


func _ready() -> void:
	load_data()


func _process(delta: float) -> void:
	_tick += delta
	if _tick < TICK:
		return
	_tick = 0.0
	_update()


# ---------------------------------------------------------------- defaults


func _defaults() -> Dictionary:
	var now := Time.get_unix_time_from_system()
	return {
		"water": {
			"enabled": true,
			"interval_min": 60,
			"goal_ml": 1500,
			"day": _today(),
			"today_ml": 0,
			"cups": 0,
			"last_remind": now,
		},
		"sit": {"enabled": true, "interval_min": 60, "since": now},
		"alarms": [],
		"memos": [],
		"sound": true,
	}


func _merge(dst: Dictionary, src: Dictionary) -> void:
	for key in src:
		var value = src[key]
		if typeof(value) == TYPE_DICTIONARY and typeof(dst.get(key)) == TYPE_DICTIONARY:
			_merge(dst[key], value)
		else:
			dst[key] = value


func load_data() -> void:
	_data = _defaults()
	if FileAccess.file_exists(data_path):
		var file := FileAccess.open(data_path, FileAccess.READ)
		if file != null:
			var raw = JSON.parse_string(file.get_as_text())
			file.close()
			if typeof(raw) == TYPE_DICTIONARY:
				_merge(_data, raw)
	_roll_day()


func _save() -> void:
	DirAccess.make_dir_recursive_absolute(data_path.get_base_dir())
	var file := FileAccess.open(data_path, FileAccess.WRITE)
	if file == null:
		push_warning("reminders: cannot write " + data_path)
		return
	file.store_string(JSON.stringify(_data, "\t"))
	file.close()


# ---------------------------------------------------------------- time


func _today() -> String:
	return Time.get_date_string_from_system()


## 0 = Sunday ... 6 = Saturday, computed from the local civil date so it does
## not depend on how Godot encodes `weekday` in date dictionaries.
func _weekday() -> int:
	var d := Time.get_date_dict_from_system()
	var ts := Time.get_unix_time_from_datetime_dict({
		"year": int(d["year"]), "month": int(d["month"]), "day": int(d["day"]),
		"hour": 0, "minute": 0, "second": 0,
	})
	return (int(ts / 86400.0) + 4) % 7


func _roll_day() -> void:
	var water: Dictionary = _data["water"]
	if str(water.get("day", "")) == _today():
		return
	water["day"] = _today()
	water["today_ml"] = 0
	water["cups"] = 0
	water["last_remind"] = Time.get_unix_time_from_system()


# ---------------------------------------------------------------- tick


func _update() -> void:
	_roll_day()
	var now := Time.get_unix_time_from_system()

	var water: Dictionary = _data["water"]
	var interval := maxf(5.0, float(water.get("interval_min", 60))) * 60.0
	if bool(water.get("enabled", true)) and today_ml() < goal_ml():
		if now - float(water.get("last_remind", now)) >= interval:
			water["last_remind"] = now
			_save()
			var left := maxi(0, goal_ml() - today_ml())
			notice.emit("water", "该喝水啦 · 还差 %d ml" % left)

	var sit: Dictionary = _data["sit"]
	var sit_gap := maxf(5.0, float(sit.get("interval_min", 60))) * 60.0
	if bool(sit.get("enabled", true)) and now - float(sit.get("since", now)) >= sit_gap:
		sit["since"] = now
		_save()
		notice.emit("sit", "坐了%s啦，起来伸个懒腰"
				% _duration_words(int(sit_gap / 60.0)))

	_check_alarms()
	_check_memos()


func _duration_words(minutes: int) -> String:
	if minutes % 60 == 0:
		return "%d小时" % int(minutes / 60.0)
	return "%d分钟" % minutes


func _check_alarms() -> void:
	var dt := Time.get_datetime_dict_from_system()
	var hm := "%02d:%02d" % [int(dt["hour"]), int(dt["minute"])]
	var stamp := _today() + " " + hm
	var wd := _weekday()
	var fired_any := false
	for alarm in _data["alarms"]:
		if typeof(alarm) != TYPE_DICTIONARY:
			continue
		if not bool(alarm.get("on", true)):
			continue
		if str(alarm.get("time", "")) != hm:
			continue
		if str(alarm.get("fired", "")) == stamp:
			continue
		var repeat := str(alarm.get("repeat", "daily"))
		if repeat == "weekdays" and (wd == 0 or wd == 6):
			continue
		alarm["fired"] = stamp
		if repeat == "once":
			alarm["on"] = false
		fired_any = true
		var label := str(alarm.get("label", ""))
		notice.emit("alarm", ("闹钟 " + hm + " · " + label) if label != "" else ("闹钟 " + hm + " 到啦"))
	if fired_any:
		_save()
		changed.emit()


func _check_memos() -> void:
	var today := _today()
	var due := false
	for memo in _data["memos"]:
		if typeof(memo) != TYPE_DICTIONARY:
			continue
		if bool(memo.get("done", false)):
			continue
		if str(memo.get("date", "")) != today:
			continue
		if str(memo.get("notified", "")) == today:
			continue
		memo["notified"] = today
		due = true
		notice.emit("memo", "今天要记得：" + str(memo.get("title", "")))
	if due:
		_save()
		changed.emit()


# ---------------------------------------------------------------- water


func today_ml() -> int:
	return int(_data["water"].get("today_ml", 0))


func cups_today() -> int:
	return int(_data["water"].get("cups", 0))


func goal_ml() -> int:
	return int(_data["water"].get("goal_ml", 1500))


func water_enabled() -> bool:
	return bool(_data["water"].get("enabled", true))


func water_interval() -> int:
	return int(_data["water"].get("interval_min", 60))


func log_water(ml: int) -> void:
	if ml <= 0:
		return
	_roll_day()
	var water: Dictionary = _data["water"]
	water["today_ml"] = today_ml() + ml
	water["cups"] = cups_today() + 1
	# Drinking restarts the "time for water" clock.
	water["last_remind"] = Time.get_unix_time_from_system()
	_save()
	water_logged.emit(ml, today_ml(), goal_ml())
	changed.emit()


func set_water_enabled(on: bool) -> void:
	_data["water"]["enabled"] = on
	_data["water"]["last_remind"] = Time.get_unix_time_from_system()
	_save()
	changed.emit()


func set_water_interval(minutes: int) -> void:
	_data["water"]["interval_min"] = clampi(minutes, 5, 240)
	_data["water"]["last_remind"] = Time.get_unix_time_from_system()
	_save()
	changed.emit()


func set_goal(ml: int) -> void:
	_data["water"]["goal_ml"] = clampi(ml, 300, 6000)
	_save()
	changed.emit()


func reset_water_day() -> void:
	_data["water"]["today_ml"] = 0
	_data["water"]["cups"] = 0
	_save()
	changed.emit()


# ---------------------------------------------------------------- sitting


func sit_enabled() -> bool:
	return bool(_data["sit"].get("enabled", true))


func sit_interval() -> int:
	return int(_data["sit"].get("interval_min", 60))


func sit_minutes() -> int:
	var since := float(_data["sit"].get("since", 0.0))
	return maxi(0, int((Time.get_unix_time_from_system() - since) / 60.0))


func set_sit_enabled(on: bool) -> void:
	_data["sit"]["enabled"] = on
	stand_up()
	changed.emit()


func set_sit_interval(minutes: int) -> void:
	_data["sit"]["interval_min"] = clampi(minutes, 5, 240)
	stand_up()


func stand_up() -> void:
	_data["sit"]["since"] = Time.get_unix_time_from_system()
	_save()
	changed.emit()


# ---------------------------------------------------------------- alarms


func alarms() -> Array:
	return _data["alarms"]


func add_alarm(time_text: String, label: String, repeat: String) -> bool:
	var hm := _normalize_time(time_text)
	if hm == "":
		return false
	_data["alarms"].append({
		"id": _new_id(),
		"time": hm,
		"label": label,
		"repeat": repeat if repeat in ["daily", "weekdays", "once"] else "daily",
		"on": true,
		"fired": "",
	})
	_data["alarms"].sort_custom(func(a, b): return str(a.get("time", "")) < str(b.get("time", "")))
	_save()
	changed.emit()
	return true


func toggle_alarm(id: String) -> void:
	for alarm in _data["alarms"]:
		if str(alarm.get("id", "")) == id:
			alarm["on"] = not bool(alarm.get("on", true))
			alarm["fired"] = ""
			_save()
			changed.emit()
			return


func remove_alarm(id: String) -> void:
	var kept: Array = []
	for alarm in _data["alarms"]:
		if str(alarm.get("id", "")) != id:
			kept.append(alarm)
	_data["alarms"] = kept
	_save()
	changed.emit()


func _normalize_time(text: String) -> String:
	var parts := text.strip_edges().replace("：", ":").split(":")
	if parts.size() != 2:
		return ""
	if not parts[0].is_valid_int() or not parts[1].is_valid_int():
		return ""
	var h := int(parts[0])
	var m := int(parts[1])
	if h < 0 or h > 23 or m < 0 or m > 59:
		return ""
	return "%02d:%02d" % [h, m]


# ---------------------------------------------------------------- memos


func memos() -> Array:
	return _data["memos"]


func add_memo(title: String, detail: String, date: String) -> bool:
	title = title.strip_edges()
	if title == "":
		return false
	date = date.strip_edges()
	if date != "" and not _valid_date(date):
		return false
	_data["memos"].append({
		"id": _new_id(),
		"title": title,
		"detail": detail.strip_edges(),
		"date": date,
		"done": false,
		"notified": "",
		"created": _today(),
	})
	_save()
	changed.emit()
	return true


func toggle_memo(id: String) -> void:
	for memo in _data["memos"]:
		if str(memo.get("id", "")) == id:
			memo["done"] = not bool(memo.get("done", false))
			_save()
			changed.emit()
			return


func remove_memo(id: String) -> void:
	var kept: Array = []
	for memo in _data["memos"]:
		if str(memo.get("id", "")) != id:
			kept.append(memo)
	_data["memos"] = kept
	_save()
	changed.emit()


func _valid_date(text: String) -> bool:
	var parts := text.split("-")
	if parts.size() != 3:
		return false
	for part in parts:
		if not part.is_valid_int():
			return false
	var y := int(parts[0])
	var m := int(parts[1])
	var d := int(parts[2])
	return y >= 2020 and y <= 2100 and m >= 1 and m <= 12 and d >= 1 and d <= 31


# ---------------------------------------------------------------- misc


func sound_on() -> bool:
	return bool(_data.get("sound", true))


func set_sound(on: bool) -> void:
	_data["sound"] = on
	_save()


func _new_id() -> String:
	return "%d_%d" % [int(Time.get_unix_time_from_system()), randi() % 100000]
