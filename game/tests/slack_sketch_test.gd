extends Node
## Dev-only: the slack state alternates between the prone reading rig and the new
## prone "doodle the whale" sketch rig.  Expiring `_slack_switch_timer` must flip
## `_slack_sketching`, swap the shown rig, and start `prone_sketch_loop`; leaving
## slack must always return to reading.  Captures both poses so the sketch art
## and its scribble loop can be eyeballed.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/slack_sketch"


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "slack-sketch",
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
	Stage.begin(self, 120.0, "FishPet slack_sketch")
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	if pet._rig_prone == null:
		_fail("prone (reading) rig failed to load")
	if pet._rig_prone_sketch == null:
		_fail("prone_sketch rig failed to load")
	if failures != 0:
		_finish()
		return

	# Slack enters on reading, and routes to the sketch rig only once the flip
	# flag is set.
	await _enter("slack", "prone")
	_check_pose("prone", "prone_read_loop", "slack starts on reading")
	await _shot(vp, "1_reading.png")

	# Expire the alternation timer: the next tick must swap to the sketch pose.
	pet._slack_switch_timer = 0.0
	await _wait_sketch()
	_check_pose("prone_sketch", "prone_sketch_loop", "expired timer flips to sketch")
	_check_flag(true)
	await _shot(vp, "2_sketch.png")

	# The scribble loop should be running on the sketch rig's own animation state.
	var entry = pet._rig_prone_sketch.get_animation_state().get_current(0)
	if entry == null or entry.get_animation().get_name() != "prone_sketch_loop":
		_fail("expected prone_sketch_loop playing, got %s"
			% ("<none>" if entry == null else entry.get_animation().get_name()))

	# Expire again: it alternates back to reading.
	pet._slack_switch_timer = 0.0
	await _enter("slack", "prone")
	_check_pose("prone", "prone_read_loop", "second expiry returns to reading")
	_check_flag(false)

	# A dangling sketch must never survive leaving slack.
	pet._slack_sketching = true
	await _enter("working", "seated")
	_check_flag(false)
	if pet._slack_sketching:
		_fail("_slack_sketching should clear once slack ends")

	_finish()


func _check_pose(rig: String, loop: String, why: String) -> void:
	print("pose rig=%s loop=%s (%s)" % [pet._pose_rig("slack"), pet._state_loop("slack"), why])
	if pet._pose_rig("slack") != rig:
		_fail("%s: _pose_rig(slack) expected %s, got %s" % [why, rig, pet._pose_rig("slack")])
	if pet._state_loop("slack") != loop:
		_fail("%s: _state_loop(slack) expected %s, got %s" % [why, loop, pet._state_loop("slack")])


func _check_flag(want: bool) -> void:
	if pet._slack_sketching != want:
		_fail("_slack_sketching expected %s, got %s" % [want, pet._slack_sketching])


func _enter(state: String, rig_name: String) -> void:
	pet._store.state = state
	pet._refresh_status()
	await _settle(rig_name)


func _wait_sketch() -> void:
	# The timer expiry happens inside _tick_slack_pose, which calls _enter_state
	# and starts the rig fade; wait until it is fully shown.
	await _settle("prone_sketch")


func _settle(rig_name: String) -> void:
	var until := Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		if pet._shown_rig == rig_name and pet._fade_dir == 0:
			return
	_fail("never settled on rig %s (shown=%s target=%s)"
		% [rig_name, pet._shown_rig, pet._target_rig])


func _shot(vp: SubViewport, name: String) -> void:
	Stage.save_png(await Stage.grab(vp), OUT + "/" + name)


func _finish() -> void:
	print("slack_sketch finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
