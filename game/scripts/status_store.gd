extends RefCounted
## Reads the state files written by hook.py and picks the session worth showing.
##
## Sessions are ranked by class first (a session waiting for input always beats
## one that is merely working), then by recency.  "done" only keeps its high
## rank for a short while so an old finished session does not outrank a live one.

const DONE_VISIBLE_SEC := 90.0
const WORKING_STALE_SEC := 3600.0

const RANK_NEEDS_INPUT := 0
const RANK_WORKING := 1
const RANK_DONE := 2
const RANK_IDLE := 4
const RANK_ENDED := 5

var dir_path := ""


func _init(path: String) -> void:
	dir_path = path


func all_sessions() -> Array:
	var out: Array = []
	var dir := DirAccess.open(dir_path)
	if dir == null:
		return out
	dir.list_dir_begin()
	var name := dir.get_next()
	while name != "":
		if not dir.current_is_dir() and name.ends_with(".json"):
			var entry := _read(dir_path.path_join(name))
			if not entry.is_empty():
				out.append(entry)
		name = dir.get_next()
	dir.list_dir_end()
	return out


func best(pinned_id: String = "") -> Dictionary:
	var sessions := all_sessions()
	if sessions.is_empty():
		return {}
	if pinned_id != "":
		for entry in sessions:
			if str(entry.get("session_id", "")) == pinned_id:
				return entry
	var now := Time.get_unix_time_from_system()
	var winner: Dictionary = {}
	var winner_score := -INF
	for entry in sessions:
		var score := _score(entry, now)
		if score > winner_score:
			winner_score = score
			winner = entry
	return winner


## State after ageing: a "done" session stops being interesting after a while,
## and a "working" session that has been silent for an hour is treated as idle
## (the process probably died).
func effective_state(entry: Dictionary) -> String:
	var state := str(entry.get("state", "idle"))
	var ts = entry.get("ts")
	var age := Time.get_unix_time_from_system() - (float(ts) if typeof(ts) == TYPE_FLOAT or typeof(ts) == TYPE_INT else 0.0)
	if state == "working" and age >= WORKING_STALE_SEC:
		return "idle"
	if state == "done" and age >= DONE_VISIBLE_SEC:
		return "idle"
	return state


func next_session(current_id: String) -> String:
	var ids: Array = []
	for entry in all_sessions():
		ids.append(str(entry.get("session_id", "")))
	ids.sort()
	if ids.is_empty():
		return ""
	var idx := ids.find(current_id)
	return str(ids[(idx + 1) % ids.size()])


func _read(path: String) -> Dictionary:
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return {}
	var data = JSON.parse_string(f.get_as_text())
	if typeof(data) != TYPE_DICTIONARY:
		return {}
	return data


func _rank(entry: Dictionary, now: float) -> int:
	var state := str(entry.get("state", "idle"))
	var ts := float(entry.get("ts", 0.0))
	var age := now - ts
	match state:
		"needs_input":
			return RANK_NEEDS_INPUT
		"working":
			return RANK_WORKING if age < WORKING_STALE_SEC else RANK_IDLE
		"done":
			return RANK_DONE if age < DONE_VISIBLE_SEC else RANK_IDLE
		"ended":
			return RANK_ENDED
		_:
			return RANK_IDLE


func _score(entry: Dictionary, now: float) -> float:
	var rank := _rank(entry, now)
	# Recency only breaks ties inside a rank, so keep it well below 1 rank step.
	var freshness := maxf(
		float(entry.get("ts", 0.0)),
		_transcript_mtime(entry)
	)
	return -float(rank) * 1.0e12 + freshness


func _transcript_mtime(entry: Dictionary) -> float:
	var path := str(entry.get("transcript_path", ""))
	if path == "" or not FileAccess.file_exists(path):
		return 0.0
	return FileAccess.get_modified_time(path)
