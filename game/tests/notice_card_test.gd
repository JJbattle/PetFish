extends Node
## Dev-only: water/sit reminders act from the bubble's action card (not the chat
## banner).  Water offers 150/250/500 ml + 稍后; sit offers the 1-minute
## follow-along, "already moved", and 稍后.  Starting the follow-along switches to
## the activity rig and drives the 60 s session, with pause/resume/end.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "notice-card",
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
	Stage.begin(self, 60.0, "FishPet notice_card")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	pet._state = "idle"
	pet._refresh_texts()

	# --- water reminder: action card with amounts + 稍后, no chat banner ---
	pet._on_notice("water", "该喝水啦 · 还差 500 ml")
	_check(not pet._chat_open, "water reminder does not open the chat")
	_check(pet._notice_card.visible, "water reminder shows the action card")
	_check(_button_texts() == ["🥤 150 ml", "🥤 250 ml", "🥤 500 ml", "稍后"],
		"water card has the three amounts and 稍后")
	_check(not pet._chat_panel._notice_banner.visible, "water keeps the chat banner down")
	await _shot(vp, "water_card.png")

	# Logging water resolves the reminder and hides the card.
	pet._on_notice_action("log_250")
	_check(not pet._notice_card.visible, "logging water hides the card")
	_check(pet._attention_clip == "" and pet._bubble_notice == "", "water reminder cleared")
	# The drink-logged notice opens the chat as a plain line (existing behavior).
	_check(pet._chat_open, "drink-logged notice opens the chat")
	pet._on_chat_closed()

	# --- sit reminder: follow-along / already moved / 稍后 ---
	pet._on_notice("sit", "坐了1小时啦，起来动动")
	_check(not pet._chat_open, "sit reminder does not open the chat")
	_check(pet._notice_card.visible, "sit reminder shows the action card")
	_check(_button_texts() == ["跟我动 1 分钟", "我已经活动了", "稍后"],
		"sit card has follow-along, already-moved and 稍后")
	await _shot(vp, "sit_card.png")

	# "跟我动" opens the package picker.
	pet._on_notice_action("activity")
	_check(_button_texts() == ["原地巡逻", "海草舒展", "肩膀放松", "返回"],
		"activity pick lists the three routines and 返回")
	await _shot(vp, "activity_pick.png")

	# Choosing 原地巡逻 starts the 60 s session on the activity rig.
	pet._on_notice_action("activity_a")
	_check(pet._activity_active, "activity starts")
	_check(pet._activity != null and pet._activity.state() == "running", "session running")
	_check(pet._activity.current_clip() == "activity_ready", "session begins with the ready pose")
	_check(pet._bubble_label.text.find("原地巡逻") != -1, "bubble reports the running package")
	_check(pet._notice_card.visible, "activity bar is up")
	_check(_button_texts() == ["暂停", "结束"], "activity bar has pause and end")
	await _shot(vp, "activity_running.png")

	# Pause / resume / end.
	pet._on_notice_action("activity_pause")
	_check(pet._activity.state() == "paused", "pause stops the clock")
	_check(_button_texts() == ["继续", "结束"], "paused bar offers 继续 and 结束")
	pet._on_notice_action("activity_resume")
	_check(pet._activity.state() == "running", "resume restarts the clock")

	pet._on_notice_action("activity_end")
	_check(not pet._activity_active, "end clears the activity flag")
	_check(pet._activity.state() == "idle", "end stops the session")
	_check(not pet._notice_card.visible or _button_texts() == ["跟我动 1 分钟", "我已经活动了", "稍后"],
		"ending early re-offers the sit card")

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
	Stage.save_png(await Stage.grab(vp), "I:/PetFish/tools/_debug/notice_card/" + name)


func _finish() -> void:
	print("notice_card finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
