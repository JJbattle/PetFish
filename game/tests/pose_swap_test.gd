extends Node
## Dev-only: the seated and prone pose rigs must swap in for the "working" and
## "slack" session states, fading through transparent so the Windows draw region
## always matches the pose that is on screen, while idle and any reminder/drink
## chain stay on the standing rig.  One PNG per state is captured for inspection.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/pose_swap"


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "pose-swap",
			"state": state,
			"ts": Time.get_unix_time_from_system(),
			"project": "PetFish",
			"transcript_path": "",
			"tool_count": 1,
			"tool_name": "",
		}

	func effective_state(entry: Dictionary) -> String:
		return str(entry.get("state", "idle"))

	func next_session(_id: String) -> String:
		return ""


var pet: Control
var failures := 0


func _ready() -> void:
	Stage.begin(self, 120.0, "FishPet pose_swap")
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	if pet._rig == null or pet._rig_seated == null or pet._rig_prone == null:
		_fail("a rig failed to load: standing=%s seated=%s prone=%s"
			% [pet._rig != null, pet._rig_seated != null, pet._rig_prone != null])
		_finish()
		return
	print("rigs standing=%s seated=%s prone=%s"
		% [pet._rig.position, pet._rig_seated.position, pet._rig_prone.position])

	await _pose("working", "seated", "seat_work_loop", "1_working_seated.png", vp)
	await _pose("slack", "prone", "prone_read_loop", "2_slack_prone.png", vp)
	await _pose("idle", "standing", "idle", "3_idle_standing.png", vp)

	_finish()


func _pose(state: String, rig_name: String, loop: String, shot: String, vp: SubViewport) -> void:
	pet._store.state = state
	pet._refresh_status()
	var until := Time.get_ticks_msec() + 8000
	var settled := false
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		if pet._shown_rig == rig_name and pet._fade_dir == 0:
			settled = true
			break
	if not settled:
		_fail("state %s never settled on rig %s (shown=%s target=%s fade=%s)"
			% [state, rig_name, pet._shown_rig, pet._target_rig, pet._fade_dir])
		return
	# The standing rig tracks its clip in `_anim`; the seated/prone rigs are
	# outside that state machine and track theirs in `_rig_loops`.
	var actual: String = pet._anim if rig_name == "standing" else str(pet._rig_loops.get(rig_name, ""))
	if actual != loop:
		_fail("state %s rig %s should loop %s, got %s" % [state, rig_name, loop, actual])
	Stage.save_png(await Stage.grab(vp), OUT + "/" + shot)
	print("pose %-7s -> %-8s loop %-15s shown=%s" % [state, rig_name, loop, pet._shown_rig])


func _finish() -> void:
	Stage.ok("pose_swap finished, failures=%d" % failures)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
