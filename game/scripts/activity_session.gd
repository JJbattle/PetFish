extends RefCounted
## Pure controller for the "跟我动 1 分钟" follow-along.  It owns the package
## config, effective-time accounting, pause and the 60 s completion, but not
## Spine playback: pet.gd reads current_clip()/current_loop() and calls
## advance(delta) with pause-free deltas, then swaps clips when current_clip()
## changes (see pet.gd _tick_activity).

const TOTAL_SECS := 60.0

## A 套 (原地巡逻), B 套 (海草舒展) and C 套 (肩膀放松) all run on the standing
## rig.  Segments sum to TOTAL_SECS and each clip loops until its segment
## elapses.  The clips live on the STANDING rig (pet_portrait.png style), so the
## follow-along shows the same character as the idle pet, not a redrawn one.
const PACKAGES := {
	"a": {
		"name": "原地巡逻",
		"segments": [
			{"clip": "needs_input", "dur": 10.0},
			{"clip": "march", "dur": 20.0},
			{"clip": "heel", "dur": 20.0},
			{"clip": "idle", "dur": 10.0},
		],
	},
	"b": {"name": "海草舒展", "segments": [
		{"clip": "needs_input", "dur": 10.0},
		{"clip": "side_bend_l", "dur": 15.0},
		{"clip": "side_bend_r", "dur": 15.0},
		{"clip": "chest_open", "dur": 15.0},
		{"clip": "idle", "dur": 5.0},
	]},
	"c": {"name": "肩膀放松", "segments": [
		{"clip": "needs_input", "dur": 10.0},
		{"clip": "shrug", "dur": 10.0},
		{"clip": "march", "dur": 20.0},
		{"clip": "chest_open", "dur": 15.0},
		{"clip": "idle", "dur": 5.0},
	]},
}

var _package := ""
var _package_name := ""
var _segments: Array = []
var _index := -1
var _seg_elapsed := 0.0
var _total := 0.0
## idle / running / paused / awaiting_confirmation
var _state := "idle"


## Begin a package.  Returns false (and stays idle) when its clips are missing.
func start(package_id: String) -> bool:
	var pkg: Dictionary = PACKAGES.get(package_id, {})
	var segs: Array = pkg.get("segments", [])
	if segs.is_empty():
		_state = "idle"
		_index = -1
		return false
	_package = package_id
	_package_name = str(pkg.get("name", ""))
	_segments = segs
	_index = -1
	_seg_elapsed = 0.0
	_total = 0.0
	_state = "running"
	_advance_segment()
	return true


func _advance_segment() -> void:
	_index += 1
	_seg_elapsed = 0.0
	if _index >= _segments.size():
		_state = "awaiting_confirmation"


## Advance effective time.  Callers pass pause-free deltas (clamped).
func advance(delta: float) -> void:
	if _state != "running" or _index < 0 or _index >= _segments.size():
		return
	_total += delta
	_seg_elapsed += delta
	if _seg_elapsed >= float(_segments[_index]["dur"]):
		_advance_segment()


func pause() -> void:
	if _state == "running":
		_state = "paused"


func resume() -> void:
	if _state == "paused":
		_state = "running"


func stop() -> void:
	_state = "idle"
	_index = -1


func state() -> String:
	return _state


func package_name() -> String:
	return _package_name


func current_clip() -> String:
	if _index < 0 or _index >= _segments.size():
		return ""
	return str(_segments[_index]["clip"])


func current_loop() -> bool:
	return true


func total_remaining() -> float:
	return maxf(0.0, TOTAL_SECS - _total)


func segment_remaining() -> float:
	if _index < 0 or _index >= _segments.size():
		return 0.0
	return maxf(0.0, float(_segments[_index]["dur"]) - _seg_elapsed)
