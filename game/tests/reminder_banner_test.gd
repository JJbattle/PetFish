extends Node
## Dev-only: an alarm/memo reminder that fires while the chat card is already open
## appears in a dedicated banner at the top of the card (not the chat log), and
## its acknowledge path clears the reminder while leaving the chat open.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "reminder-banner",
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
	Stage.begin(self, 60.0, "FishPet reminder_banner")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	pet._state = "idle"
	pet._refresh_texts()

	# Open the chat first, as if the user is already talking.
	pet._open_chat()
	_check(pet._chat_open and pet._chat_panel.visible, "chat open before the reminder")
	_check(not pet._chat_panel._notice_banner.visible, "banner hidden before any reminder")

	# An alarm reminder fires while the chat is open.
	pet._on_notice("alarm", "闹钟响啦，休息一下眼睛")
	_check(pet._chat_panel._notice_banner.visible, "reminder banner appears above the chat")
	_check(pet._chat_panel._notice_label.text.find("闹钟响啦") != -1, "banner shows the reminder text")
	_check(_log_text().find("闹钟响啦") == -1, "reminder is not appended to the chat log")
	_check(pet._attention_clip != "", "reminder still pending")
	_check(pet._chat_open, "chat stays open while the reminder is up")
	await _shot(vp, "banner_open.png")

	# Acknowledge it; the chat card stays open.
	_check(pet._chat_panel.dismissed.is_connected(pet._on_reminder_dismissed), "banner wired to dismiss")
	pet._chat_panel.dismissed.emit()
	_check(not pet._chat_panel._notice_banner.visible, "banner hides after acknowledge")
	_check(pet._attention_clip == "" and pet._bubble_notice == "", "reminder cleared after acknowledge")
	_check(pet._chat_open and pet._chat_panel.visible, "chat stays open after acknowledge")
	await _shot(vp, "banner_dismissed.png")

	_finish()


func _log_text() -> String:
	var parts := ""
	for child in pet._chat_panel._log.get_children():
		if child is Label:
			parts += child.text + "\n"
	return parts


func _check(cond: bool, why: String) -> void:
	if not cond:
		_fail(why)
	else:
		print("ok: ", why)


func _shot(vp: SubViewport, name: String) -> void:
	Stage.save_png(await Stage.grab(vp), "I:/PetFish/tools/_debug/reminder_banner/" + name)


func _finish() -> void:
	print("reminder_banner finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
