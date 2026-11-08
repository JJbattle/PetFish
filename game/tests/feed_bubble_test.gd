extends Node
## Dev-only: a weekly feed arrives -> the bubble prompts without opening the chat;
## clicking the bubble (consent) opens the chat and shows the full item as a
## yellow bold line instead of squashing it into the two-line bubble.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "feed-bubble",
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
	Stage.begin(self, 60.0, "FishPet feed_bubble")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	# A new weekly feed arrives while idle: bubble prompt, no chat, content hidden.
	pet._state = "idle"
	pet._on_feed_ready("这是本周的同步内容：记得喝水")
	_check(pet._feed_pending, "feed 到达后进入待确认")
	_check(not pet._chat_open, "feed 不自动展开聊天卡")
	_check(pet._bubble_label.text.find("有新同步内容") != -1, "气泡显示提示")
	_check(pet._bubble_label.text.find("记得喝水") == -1, "未同意前不泄露内容")

	# Clicking the bubble = consent: open the chat and show the full item there.
	var ev := InputEventMouseButton.new()
	ev.button_index = MOUSE_BUTTON_LEFT
	ev.pressed = true
	ev.position = pet._bubble_rect.get_center()
	pet._input(ev)
	_check(not pet._feed_pending, "点击后清除待确认")
	_check(pet._chat_open, "点击气泡展开聊天卡显示内容")
	_check(_chat_log().find("记得喝水") != -1, "内容进入聊天记录")
	_check(pet._bubble_label.text.find("记得喝水") == -1, "气泡不再塞内容")
	_check(_feed_label_color_is_yellow(), "同步内容用黄色字体")
	_check(_feed_label_is_bold(), "同步内容用加粗字体")

	_finish()


func _chat_log() -> String:
	var parts := ""
	for child in pet._chat_panel._log.get_children():
		if child is Label:
			parts += child.text + "\n"
	return parts


func _feed_label() -> Label:
	for child in pet._chat_panel._log.get_children():
		if child is Label and child.text.find("记得喝水") != -1:
			return child
	return null


func _feed_label_color_is_yellow() -> bool:
	var label := _feed_label()
	return label != null and label.get_theme_color("font_color") == pet._chat_panel.C_FEED


func _feed_label_is_bold() -> bool:
	var label := _feed_label()
	return label != null and label.get_theme_font("font") != pet._chat_panel._font


func _check(cond: bool, why: String) -> void:
	if cond:
		print("ok: ", why)
	else:
		_fail(why)


func _finish() -> void:
	print("feed_bubble finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
