extends Node
## Dev-only: the chat panel opens with a greeting, sending with no API key shows
## the "no key" hint, and a mocked DeepSeek success body parses into a reply.
## No network: `_deepseek._api_key` is forced empty and `_on_done` is driven
## directly with a synthetic body.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "chat",
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
	Stage.begin(self, 60.0, "FishPet chat_panel")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	if pet._chat_panel == null:
		_fail("chat panel missing")
		_finish()
		return
	if pet._deepseek == null:
		_fail("deepseek client missing")
		_finish()
		return

	# In idle the chat is collapsed into the bubble (the entry itself); the full
	# card opens only when the bubble is clicked.
	pet._state = "idle"
	pet._refresh_texts()
	_check(pet._bubble.visible, "collapsed bubble visible at start")
	_check(not pet._chat_panel.visible, "chat card hidden at start")
	_check(not pet._chat_open, "not actively open at start")
	_check(pet._bubble_label.text.find("和大肥鱼聊聊") != -1, "idle bubble shows the prompt")
	await _shot(vp, "collapsed.png")
	pet._open_chat()
	await _frames(1)
	_check(pet._chat_panel.visible, "chat visible after open")
	_check(pet._chat_open, "_chat_open flag set")
	_check(not pet._bubble.visible, "bubble hidden while open")
	_check(_history_text().find("主人想和我聊什么呀") != -1, "greeting shown")
	await _shot(vp, "open.png")

	# No-key send must surface the hint without touching the network.
	pet._deepseek._api_key = ""
	pet._chat_panel._entry.text = "你好"
	pet._chat_panel._on_submit()
	_check(_history_text().find("还没有 API key") != -1, "no-key hint shown")

	# Mock a successful DeepSeek response and confirm it parses to a reply line.
	var body: String = JSON.stringify({"choices": [{"message": {"content": "主人好呀～"}}]})
	pet._deepseek._on_done(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), body.to_utf8_buffer())
	_check(_history_text().find("主人好呀～") != -1, "mocked reply parsed")

	# Closing collapses back to the bubble, which now shows her last reply.
	pet._close_chat()
	_check(not pet._chat_panel.visible, "chat collapses after close")
	_check(pet._bubble.visible, "bubble returns after close")
	_check(not pet._chat_open, "_chat_open cleared")
	_check(pet._bubble_label.text.find("主人好呀～") != -1, "bubble shows her last reply")
	await _shot(vp, "collapsed_reply.png")

	_finish()


func _history_text() -> String:
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


func _frames(n: int) -> void:
	for i in n:
		await get_tree().process_frame


func _shot(vp: SubViewport, name: String) -> void:
	Stage.save_png(await Stage.grab(vp), "I:/PetFish/tools/_debug/chat_panel/" + name)


func _finish() -> void:
	print("chat_panel finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
