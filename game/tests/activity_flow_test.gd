extends Node
## Dev-only: the A 套 60 s follow-along runs to completion through the whole
## clip sequence (ready -> march -> heel -> relax), then offers the completion
## confirmation on the activity bar.  Fast-forwards by driving _tick_activity
## directly instead of waiting a real minute.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "activity-flow",
			"state": state,
			"ts": Time.get_unix_time_from_system(),
			"project": "PetFish",
			"transcript_path": "",
			"tool_count": 0,
			"tool_name": "",
		}

	func effective_state(entry: Dictionary) -> String:
		return str(entry.get("state", "idle"))

	func next_session(_id: String) -> String:
		return ""


var pet: Control
var failures := 0


func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet activity_flow")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	pet._state = "idle"
	pet._refresh_texts()

	# Sit reminder -> follow-along -> A 套.
	pet._on_notice("sit", "坐了1小时啦，起来动动")
	pet._on_notice_action("activity")
	pet._on_notice_action("activity_a")
	_check(pet._activity_active and pet._activity.state() == "running", "A 套 running")

	# Hover and right-click are non-exercise operations: neither may open the info
	# card or the menu (which would turn her away from the exercise pose).
	pet._test_pointer = Vector2(168, 350)  # over the pet's body
	pet._update_hover(1.0)
	_check(not pet._menu_open and not pet._panel.visible,
		"hover during activity does not open the info card or menu")
	var rclick := InputEventMouseButton.new()
	rclick.button_index = MOUSE_BUTTON_RIGHT
	rclick.pressed = true
	rclick.position = Vector2(168, 350)
	pet._input(rclick)
	_check(not pet._menu_open, "right-click during activity does not open the menu")
	pet._test_pointer = Vector2(-9999, -9999)

	# Fast-forward 60 s in 0.5 s steps and record the clip sequence.
	var seq: Array = []
	var last := ""
	for _i in 130:
		pet._tick_activity(0.5)
		if pet._activity == null:
			break
		var clip: String = pet._activity.current_clip()
		if clip != last:
			last = clip
			seq.append(clip)
	_check(seq == ["activity_ready", "activity_march_cycle",
			"activity_heel_cycle", "activity_relax", ""],
		"clip sequence runs ready -> march -> heel -> relax, then finishes (got %s)" % str(seq))

	# Completion: activity ends and the confirmation replaces the bar.
	_check(not pet._activity_active, "activity ends at 60 s")
	_check(_button_texts() == ["完成活动", "暂不记录"], "completion confirmation shown")

	# Recording the completion stands the user up and clears everything.
	pet._on_notice_action("activity_done")
	_check(not pet._notice_card.visible, "completion hides the card")
	_check(pet._attention_clip == "" and pet._bubble_notice == "", "completion clears the reminder")
	await _shot(vp, "done.png")

	_finish()


func _button_texts() -> Array:
	var out: Array = []
	for child in pet._notice_card_box.get_children():
		if child is Button:
			out.append(child.text)
	return out


func _check(cond: bool, why: String) -> void:
	if not cond:
		_fail(why)
	else:
		print("ok: ", why)


func _shot(vp: SubViewport, name: String) -> void:
	Stage.save_png(await Stage.grab(vp), "I:/PetFish/tools/_debug/activity_flow/" + name)


func _finish() -> void:
	print("activity_flow finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
