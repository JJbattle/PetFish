extends Node
## Dev-only: the chat card auto-collapses to the bubble after COLLAPSE_IDLE
## seconds with no hover and no typing.  Hovering or typing resets the timer, and
## a pending reminder survives the collapse (it becomes the bubble line instead
## of being dismissed).

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	var state: String = "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "chat-collapse",
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
var _collapsed := 0
var _orig_mouse := Vector2i.ZERO


func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet chat_collapse")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	_orig_mouse = DisplayServer.mouse_get_position()
	var cp = pet._chat_panel
	cp.collapse.connect(func() -> void: _collapsed += 1)

	pet._state = "idle"
	pet._refresh_texts()
	_check(cp.COLLAPSE_IDLE == 5.0, "idle threshold is 5 s")
	_check(cp.collapse.is_connected(pet._close_chat), "collapse wired to _close_chat")

	# An alarm reminder opens the chat; it must survive a collapse as a bubble line.
	pet._on_notice("alarm", "闹钟响啦，起来动动")
	_check(pet._chat_open and cp.visible, "reminder opens the chat")

	# Typing resets the idle timer.
	cp._idle = 5.0
	cp._on_entry_changed("x")
	_check(cp._idle == 0.0, "typing resets the idle timer")

	# Hover holds the card open: put the cursor on the card and drive past the
	# threshold; nothing should collapse.
	var rect: Rect2 = cp.get_global_rect()
	_warp(rect.get_center())
	cp._idle = cp.COLLAPSE_IDLE - 0.1
	cp._process(0.2)
	_check(_collapsed == 0 and cp.visible, "hover holds the card open past the threshold")

	# Idle (cursor off the card) past the threshold collapses it to the bubble.
	_warp(Vector2(700.0, 470.0))
	# The ✕ ring drains with the idle timer: half the threshold means half left.
	cp._idle = cp.COLLAPSE_IDLE * 0.5
	cp._process(0.0)
	_check(cp._close_ring != null, "close ring exists")
	_check(absf(cp._ring_value - 0.5) < 0.01, "ring drains with the idle countdown")
	cp._idle = cp.COLLAPSE_IDLE - 0.1
	cp._process(0.2)
	_check(_collapsed >= 1, "idle past the threshold emits collapse")
	_check(not pet._chat_open, "collapse folds the card")
	_check(not cp.visible, "card hidden after collapse")
	_check(pet._bubble.visible, "bubble returns after collapse")
	_check(pet._bubble_label.text.find("闹钟响啦") != -1, "reminder survives as a bubble line")
	_check(pet._attention_clip != "", "collapse does not dismiss the reminder")

	_finish()


func _warp(canvas_pos: Vector2) -> void:
	# The stage SubViewport sits at the window's origin, so window-local == canvas.
	DisplayServer.warp_mouse(DisplayServer.window_get_position() + Vector2i(canvas_pos))


func _check(cond: bool, why: String) -> void:
	if not cond:
		_fail(why)
	else:
		print("ok: ", why)


func _finish() -> void:
	DisplayServer.warp_mouse(_orig_mouse)
	print("chat_collapse finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
