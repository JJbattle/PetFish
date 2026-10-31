extends Node
## Dev-only: open the right-click menu and the settings card while the pet is in
## each base state, then close them and check she goes back to that state with
## nothing left in her hands and nothing left in the queue.
##
## Run: godot --path game --rendering-driver opengl3 res://tests/state_cards_test.tscn

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state := "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "cards",
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


func _ready() -> void:
	Stage.begin(self, 110.0, "FishPet state_cards")
	var vp := Stage.make_stage(self, Vector2i(380, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	store = FakeStore.new()
	pet._store = store
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	for entry in [
		["working", "menu"],
		["slack", "settings"],
		["needs_input", "menu"],
	]:
		await _check(str(entry[0]), str(entry[1]))

	Stage.ok("state cards checked, failures=%d" % failures)


func _check(state: String, card: String) -> void:
	store.state = state
	pet._refresh_status()
	if not await _wait_anim(_base_anim(state), 8.0):
		_fail("%s: never reached its base clip (at %s)" % [state, pet._anim])
		return
	await get_tree().create_timer(0.4).timeout
	print("  %s: base=%s book=%s" % [state, pet._anim, _att("book")])
	if card == "menu":
		pet._set_menu_open(true)
	else:
		pet._open_settings()
	if not await _wait_present(6.0):
		_fail("%s: opening the %s never raised a present pose (at %s)"
			% [state, card, pet._anim])
	if card == "menu":
		pet._set_menu_open(false)
	else:
		pet._close_settings()
	# she should drop the offer and be back in the state's own clip, holding
	# whatever that state holds, with nothing queued behind it
	if not await _wait_anim(_base_anim(state), 8.0):
		_fail("%s: did not return after closing the %s (at %s)"
			% [state, card, pet._anim])
		return
	await get_tree().create_timer(0.6).timeout
	if pet._queue.size() != 0:
		_fail("%s: %d item(s) left in the queue" % [state, pet._queue.size()])
	# working holds the notebook, slack cradles the whale; both must be back in
	# her hands, and neither may linger in the states that carry no prop
	var slot := "fish" if state == "slack" else "book"
	var want := "1.00" if state in ["working", "slack"] else "nil"
	if _att(slot) != want:
		_fail("%s: %s should be %s after closing, is %s"
			% [state, slot, want, _att(slot)])
	print("  %s: back to %s, queue=%d, %s=%s, ok"
		% [state, pet._anim, pet._queue.size(), slot, _att(slot)])


func _att(slot_name: String) -> String:
	var s = pet._rig.get_skeleton().find_slot(slot_name)
	if s == null or s.get_attachment() == null:
		return "nil"
	return "%.2f" % s.get_color().a


func _base_anim(state: String) -> String:
	match state:
		"working":
			return "working"
		"slack":
			return "slack"
		_:
			return "needs_input"


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
