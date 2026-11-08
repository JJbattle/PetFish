extends Node
## Dev-only: the chat collapses into a bubble, hovering the pet shows the right
## cards without hiding the bubble, clicking the bubble expands the chat, and
## clicking elsewhere collapses it again.  A reminder also survives as a bubble
## line until the ✕ acknowledges it.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "bubble-chat",
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
	Stage.begin(self, 60.0, "FishPet bubble_chat")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	# Idle: collapsed bubble, hidden card.
	pet._state = "idle"
	pet._refresh_texts()
	_check(pet._bubble.visible and not pet._chat_panel.visible, "idle collapses to bubble")
	_check(pet._bubble_label.text.find("和大肥鱼聊聊") != -1, "idle bubble prompt")
	await _shot(vp, "idle_bubble.png")

	# Hovering raises the right cards but keeps the bubble up.
	pet._show_panel(true)
	pet._set_menu_open(true)
	_check(pet._panel.visible, "hover raises the info card")
	_check(pet._bubble.visible, "bubble stays while hovering")
	await _shot(vp, "hover.png")
	pet._set_menu_open(false)
	pet._show_panel(false)

	# Clicking the bubble expands the chat.
	pet._open_chat()
	_check(pet._chat_open, "_chat_open flag set")
	_check(pet._chat_panel.visible and not pet._bubble.visible, "click expands the chat")

	# Clicking elsewhere collapses it back to the bubble.
	pet._close_chat()
	_check(pet._bubble.visible and not pet._chat_panel.visible, "click away collapses to bubble")
	_check(not pet._chat_open, "_chat_open cleared after collapse")

	# A sit reminder acts from the bubble: it does not open the chat card; it shows
	# the reminder line plus an action card above the bubble, and the ✕ (dismiss)
	# clears both.
	pet._on_notice("sit", "坐太久了，起来动动")
	_check(not pet._chat_open, "sit reminder does not open the chat")
	_check(pet._notice_card.visible, "sit reminder shows the action card")
	_check(pet._bubble_notice.find("坐太久了") != -1, "reminder text saved for the bubble")
	_check(pet._bubble_label.text.find("坐太久了") != -1, "bubble shows the reminder")
	_check(pet._attention_clip != "", "reminder still pending")
	await _shot(vp, "sit_card.png")
	pet._on_chat_closed()
	_check(pet._attention_clip == "" and pet._bubble_notice == "", "dismiss clears the reminder")
	_check(not pet._notice_card.visible, "dismiss hides the action card")
	_check(pet._bubble_label.text.find("和大肥鱼聊聊") != -1, "bubble returns to the prompt after dismiss")

	_finish()


func _check(cond: bool, why: String) -> void:
	if not cond:
		_fail(why)
	else:
		print("ok: ", why)


func _shot(vp: SubViewport, name: String) -> void:
	Stage.save_png(await Stage.grab(vp), "I:/PetFish/tools/_debug/bubble_chat/" + name)


func _finish() -> void:
	print("bubble_chat finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
