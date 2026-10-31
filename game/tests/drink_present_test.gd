extends Node
## Dev-only: verify the two recent fixes.
##   1. bubble / panel / menu / settings track the 170 px pet (derived in
##      _layout_ui from _pet_rect) instead of hard-coded rects.
##   2. a drink requested while a card is up (the right-click menu is still open
##      when "喝水打卡" logs the water) lowers the offered hand first, then drinks,
##      then returns to the base pose -- never the old
##      present -> drink -> present -> idle hiccup.
##
## Run: godot --path game --rendering-driver opengl3 res://tests/drink_present_test.tscn

const Stage = preload("res://tests/test_stage.gd")

const DRINK := ["drink_in", "drink_sip", "drink_out"]


class FakeStore extends RefCounted:
	var state := "working"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "drink",
			"state": state,
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
var store: FakeStore
var failures := 0
var seq: Array = []


func _ready() -> void:
	Stage.begin(self, 120.0, "FishPet drink_present")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	store = FakeStore.new()
	pet._store = store
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	_check_layout()

	store.state = "working"
	pet._refresh_status()
	if not await _wait_anim("working", 8.0):
		_fail("never reached working base (at %s)" % pet._anim)
		Stage.ok("drink_present finished, failures=%d" % failures)
		return

	# open the menu and wait for the offered hand to hold
	pet._set_menu_open(true)
	if not await _wait_present(6.0):
		_fail("opening the menu never raised a present pose (at %s)" % pet._anim)
		Stage.ok("drink_present finished, failures=%d" % failures)
		return
	print("menu open: phase=%s anim=%s" % [pet._present_phase, pet._anim])

	# 喝水打卡 logs water while the menu is still up, then closes it
	pet.start_chain(DRINK.duplicate())
	await get_tree().process_frame
	await get_tree().process_frame
	print("after start_chain: phase=%s anim=%s queue=%d chain=%d"
		% [pet._present_phase, pet._anim, pet._queue.size(), pet._chain.size()])
	if pet._present_phase != "out":
		_fail("start_chain during present should lower the hand first (phase=%s)"
			% pet._present_phase)
	if pet._chain.size() != 0:
		_fail("drink should be queued, not started, while the hand lowers (chain=%d)"
			% pet._chain.size())
	pet._set_menu_open(false)

	# follow the whole thing back to the base pose, recording distinct
	# (anim, phase) transitions
	await _track(15.0)

	var idx := -1
	for i in seq.size():
		var s: String = seq[i]
		if s.begins_with("drink_in"):
			idx = i
			break
	var lowered := -1
	for i in seq.size():
		var s: String = seq[i]
		if s.begins_with("present_out"):
			lowered = i
			break
	if lowered < 0 or idx < 0:
		_fail("expected present_out then drink_in, saw %s" % str(seq))
	elif lowered >= idx:
		_fail("present_out must precede drink_in: %s" % str(seq))

	var last_drink := -1
	for i in seq.size():
		if seq[i].begins_with("drink_out"):
			last_drink = i
	for i in range(last_drink + 1, seq.size()):
		var s: String = seq[i]
		if s.begins_with("present") or s.begins_with("present_out"):
			_fail("presentation re-appeared after the drink: %s" % str(seq))
			break

	if pet._queue.size() != 0:
		_fail("%d item(s) left in the queue" % pet._queue.size())
	if pet._anim != "working":
		_fail("did not return to working after drinking (at %s)" % pet._anim)

	Stage.ok("drink_present finished, failures=%d" % failures)


func _check_layout() -> void:
	print("LAYOUT pet_rect=%s" % pet._pet_rect)
	print("LAYOUT bubble=%s (pet.top=%.1f)" % [pet._bubble_rect, pet._pet_rect.position.y])
	print("LAYOUT panel=%s menu_pos=%s settings=%s (pet.right=%.1f)"
		% [pet._panel_rect, pet._menu_pos, pet._settings_rect, pet._pet_rect.end.x])
	if pet._bubble_rect.end.y > pet._pet_rect.position.y:
		_fail("bubble should sit above the head: bubble=%s pet.top=%.1f"
			% [pet._bubble_rect, pet._pet_rect.position.y])
	if pet._panel_rect.position.x < pet._pet_rect.end.x:
		_fail("panel should sit right of the pet: panel=%s pet.right=%.1f"
			% [pet._panel_rect, pet._pet_rect.end.x])
	if pet._settings_rect.position.x < pet._pet_rect.end.x:
		_fail("settings should sit right of the pet: settings=%s pet.right=%.1f"
			% [pet._settings_rect, pet._pet_rect.end.x])


func _track(secs: float) -> void:
	var until := Time.get_ticks_msec() + int(secs * 1000.0)
	while Time.get_ticks_msec() < until:
		await get_tree().process_frame
		var cur := "%s/%s" % [pet._anim, pet._present_phase]
		if seq.is_empty() or seq[-1] != cur:
			seq.append(cur)
		if pet._present_phase == "" and pet._anim == "working" \
				and not pet._chain_busy() and pet._queue.is_empty():
			return
	print("SEQ ", str(seq))


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
		if pet._present_phase == "hold":
			return true
		await get_tree().process_frame
	return false


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
