extends Node
## Dev-only: writing into a settings field should turn the offered card into
## "she holds the notebook and jots it down", then back to the offer when the
## typing stops, and closing the card must leave nothing sticking.
##
## Run: godot --path game --rendering-driver opengl3 res://tests/note_take_test.tscn

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/note_take"


class FakeStore extends RefCounted:
	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "notes",
			"state": "working",
			"ts": Time.get_unix_time_from_system(),
			"project": "PetFish",
			"transcript_path": "",
			"tool_count": 1,
			"tool_name": "Edit",
		}

	func effective_state(entry: Dictionary) -> String:
		return str(entry.get("state", "idle"))

	func next_session(_id: String) -> String:
		return ""


var pet: Control
var failures := 0
var seq: Array = []


func _ready() -> void:
	Stage.begin(self, 120.0, "FishPet note_take")
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	if not await _wait_rig("seated", 8.0):
		_fail("never reached the working base (shown=%s)" % pet._shown_rig)
		_finish()
		return

	pet._open_settings()
	if not await _wait_present(6.0):
		_fail("opening settings never raised the offer (at %s)" % pet._anim)
		_finish()
		return
	print("settings open: clip=%s anim=%s typing=%s"
		% [pet._present_clip, pet._anim, pet._settings.is_typing()])
	if pet._present_clip != "present2":
		_fail("settings should offer with present2, got %s" % pet._present_clip)

	# focus a text field the way a click does, then type into it
	var edit := _find_edit(pet._settings)
	if edit == null:
		_fail("no LineEdit found in the settings card")
		_finish()
		return
	edit.grab_focus()
	edit.insert_text_at_caret("写点东西")
	if not pet._settings.is_typing():
		_fail("is_typing() stayed false after focusing and typing")

	# the swap runs through working_in, so wait for the writing loop itself
	var noting := false
	var until := Time.get_ticks_msec() + 8000
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		_track()
		if pet._anim == "working" and pet._present_phase == "hold" and not pet._chain_busy():
			noting = true
			break
	print("typing: clip=%s anim=%s" % [pet._present_clip, pet._anim])
	Stage.save_png(await Stage.grab(vp), OUT + "/1_writing.png")
	if not noting:
		_fail("typing never reached the notebook (anim=%s clip=%s)"
			% [pet._anim, pet._present_clip])
	elif pet._present_clip != "working":
		_fail("the held clip should be the writing loop, got %s" % pet._present_clip)

	# stop writing: the offer comes back on its own
	var stopped := false
	until = Time.get_ticks_msec() + 12000
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		_track()
		if pet._anim == "present2" and pet._present_phase == "hold" and not pet._chain_busy():
			stopped = true
			break
	if not stopped:
		_fail("did not return to the offer after typing stopped (anim=%s clip=%s)"
			% [pet._anim, pet._present_clip])
	Stage.save_png(await Stage.grab(vp), OUT + "/2_offer_back.png")

	# Write again, then close the card mid-write: the session state wants the
	# very loop she is holding, so the pad must stay in her hands instead of
	# being stowed and taken straight back out.
	# a real keystroke; insert_text_at_caret() is programmatic and emits nothing
	edit.text_changed.emit(edit.text)
	if not await _wait_anim("working", 8.0):
		_fail("second round never picked the notebook up again (at %s)" % pet._anim)
		_finish()
		return
	var mark := seq.size()
	pet._close_settings()
	until = Time.get_ticks_msec() + 8000
	var kept := false
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		_track()
		if pet._anim == "working" and pet._present_phase == "" \
				and not pet._chain_busy() and pet._queue.is_empty():
			kept = true
			break
	if not kept:
		_fail("closing mid-write did not land back in working (anim=%s phase=%s)"
			% [pet._anim, pet._present_phase])
	for i in range(mark, seq.size()):
		var step: String = seq[i]
		if step.begins_with("working_out") or step.begins_with("present"):
			_fail("closing mid-write stowed and re-took the pad: %s" % str(seq.slice(mark)))
			break

	# closing the card must not leave the queue or the offer behind
	pet._close_settings()
	until = Time.get_ticks_msec() + 12000
	var home := false
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		_track()
		if pet._anim == "working" and pet._present_phase == "" \
				and not pet._chain_busy() and pet._queue.is_empty():
			home = true
			break
	if not home:
		_fail("did not settle back into the session state (anim=%s phase=%s queue=%d)"
			% [pet._anim, pet._present_phase, pet._queue.size()])
	print("SEQ ", str(seq))
	_finish()


func _find_edit(node: Node) -> LineEdit:
	if node is LineEdit:
		return node as LineEdit
	for child in node.get_children():
		var found := _find_edit(child)
		if found != null:
			return found
	return null


func _track() -> void:
	var cur := "%s/%s" % [pet._anim, pet._present_phase]
	if seq.is_empty() or seq[-1] != cur:
		seq.append(cur)


func _wait_rig(rig_name: String, secs: float) -> bool:
	var until := Time.get_ticks_msec() + int(secs * 1000.0)
	while Time.get_ticks_msec() < until:
		if pet._shown_rig == rig_name and pet._fade_dir == 0:
			return true
		await get_tree().process_frame
	return false


func _wait_anim(anim: String, secs: float) -> bool:
	var until := Time.get_ticks_msec() + int(secs * 1000.0)
	while Time.get_ticks_msec() < until:
		if pet._anim == anim and not pet._chain_busy():
			return true
		await get_tree().process_frame
	return false


func _wait_present(secs: float) -> bool:
	var until := Time.get_ticks_msec() + int(secs * 1000.0)
	while Time.get_ticks_msec() < until:
		_track()
		if pet._present_phase == "hold" and not pet._chain_busy():
			return true
		await get_tree().process_frame
	return false


func _finish() -> void:
	Stage.ok("note_take finished, failures=%d" % failures)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
