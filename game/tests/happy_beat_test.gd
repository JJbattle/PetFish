extends Node
## Dev-only: the slack (prone reading) rig must occasionally flip its face to the
## "偷着乐" happy attachments and back, and always snap to neutral when slack ends.
## Drives `_tick_happy` by expiring `_happy_timer`, then checks the spine-godot
## set_attachment path on the prone_eyes / prone_mouth slots, and captures the two
## faces so the happy art can be eyeballed.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/happy_beat"


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "happy-beat",
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
	Stage.begin(self, 120.0, "FishPet happy_beat")
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	if pet._rig_prone == null:
		_fail("prone rig failed to load")
		_finish()
		return

	await _enter("slack", "prone")
	_check_face("neutral", "slack starts neutral")
	await _shot(vp, "1_neutral.png")

	# Expire the cooldown: the next tick must flip the face to happy.
	pet._happy_timer = 0.0
	await _frames(3)
	_check_face("happy", "expired cooldown flips to happy")
	if not pet._happy:
		_fail("_happy flag should be set once the beat starts")
	await _shot(vp, "2_happy.png")

	# A beat lasts 2-3 s; force its end and confirm it drops back to neutral.
	pet._happy_timer = 0.0
	await _frames(3)
	_check_face("neutral", "beat end returns to neutral")
	await _shot(vp, "3_back_neutral.png")

	# A lingering happy face must not survive leaving slack.
	pet._set_happy(true)
	await _enter("working", "seated")
	_check_face("neutral", "leaving slack snaps the face back to neutral")
	if pet._happy:
		_fail("_happy flag should clear once slack ends")

	_finish()


func _enter(state: String, rig_name: String) -> void:
	pet._store.state = state
	pet._refresh_status()
	var until := Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		if pet._shown_rig == rig_name and pet._fade_dir == 0:
			return
	_fail("state %s never settled on rig %s (shown=%s target=%s)"
		% [state, rig_name, pet._shown_rig, pet._target_rig])


func _att(slot: String) -> String:
	var att = pet._rig_prone.get_skeleton().find_slot(slot).get_attachment()
	return "<none>" if att == null else str(att.get_attachment_name())


func _check_face(want: String, why: String) -> void:
	var eyes := _att("prone_eyes")
	var mouth := _att("prone_mouth")
	print("face eyes=%s mouth=%s (%s)" % [eyes, mouth, why])
	if eyes != want or mouth != want:
		_fail("%s: expected %s, got eyes=%s mouth=%s" % [why, want, eyes, mouth])


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _shot(vp: SubViewport, name: String) -> void:
	Stage.save_png(await Stage.grab(vp), OUT + "/" + name)


func _finish() -> void:
	Stage.ok("happy_beat finished, failures=%d" % failures)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
