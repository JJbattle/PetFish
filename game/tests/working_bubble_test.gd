extends Node
## Dev-only: the collapsed bubble is the chat entry in every state — it shows the
## idle prompt, then live progress while "working".  Reminders land in the chat
## panel (auto-opening it), not the bubble.  Tail fields are injected directly so
## the check does not depend on a real transcript file.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "working"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "working-bubble",
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
	Stage.begin(self, 120.0, "FishPet working_bubble")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	# Idle: the chat is collapsed into the bubble (showing the prompt); the full
	# card stays hidden until the bubble is clicked.
	pet._state = "idle"
	pet._refresh_texts()
	_expect(true, "💬 和大肥鱼聊聊…", "idle collapses the chat into the bubble")
	if pet._chat_panel.visible:
		_fail("idle should hide the chat card until the bubble is clicked")

	# Working with no tool seen yet: a bare "working" hint.
	pet._state = "working"
	pet._tail.tool_name = ""
	pet._tail.detail = ""
	pet._tail.tool_count = 0
	pet._refresh_texts()
	_expect(true, "干活中…", "working with no tool shows a hint")

	# Working with a tool in flight: tool + detail + step count.
	pet._tail.tool_name = "Edit"
	pet._tail.detail = "main.tscn"
	pet._tail.tool_count = 5
	pet._refresh_texts()
	_expect(true, "Edit · main.tscn\n第 5 步", "working shows tool + step progress")

	# A long detail is capped so the step line still fits.
	pet._tail.detail = "List files in the current directory and print sizes"
	pet._refresh_texts()
	var text: String = pet._bubble_label.text
	if text.find("\n第 5 步") < 0:
		_fail("long detail should keep the step line: %s" % text)
	elif text.find("…") < 0:
		_fail("long detail should be capped: %s" % text)
	pet._tail.detail = "main.tscn"

	# A notice routes into the chat panel now, not the bubble: it opens the chat
	# (hiding the bubble) and lands in the chat log; closing the chat brings the
	# working progress back.
	pet._show_notice("陪你喝了 250 ml")
	_expect(false, "", "notice opens the chat, hiding the bubble")
	if _chat_log_text().find("🔔 陪你喝了 250 ml") < 0:
		_fail("notice should land in the chat log")
	pet._on_chat_closed()
	_expect(true, "Edit · main.tscn\n第 5 步", "progress returns after closing chat")

	_finish()


func _chat_log_text() -> String:
	var parts := ""
	for child in pet._chat_panel._log.get_children():
		if child is Label:
			parts += child.text + "\n"
	return parts


func _expect(visible: bool, text: String, why: String) -> void:
	print("bubble visible=%s text=%s (%s)" % [str(pet._bubble.visible), str(pet._bubble_label.text), why])
	if pet._bubble.visible != visible:
		_fail("%s: bubble.visible=%s" % [why, str(pet._bubble.visible)])
	if text != "" and pet._bubble_label.text != text:
		_fail("%s: expected=%s got=%s" % [why, text, str(pet._bubble_label.text)])


func _finish() -> void:
	print("working_bubble finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
