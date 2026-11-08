extends Node
## Dev-only: the "AI 聊天" settings tab stores a DeepSeek key through a masked
## field.  Saving hides the key (field cleared, status flips to configured) and
## persists it to the *preview* secrets file -- the real user://secrets.json is
## never touched because test_window points deepseek at a per-process path.

const Stage = preload("res://tests/test_stage.gd")


class FakeStore extends RefCounted:
	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "key",
			"state": "idle",
			"ts": Time.get_unix_time_from_system(),
			"project": "",
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
	Stage.begin(self, 60.0, "FishPet deepseek_key")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	pet._store = FakeStore.new()
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)

	var s: Control = pet._settings
	_check(s != null, "settings card exists")
	_check(pet._deepseek != null, "deepseek client exists")
	# deterministic: ignore any DEEPSEEK_API_KEY in the test shell
	pet._deepseek._api_key = ""

	# The key setting is the fifth tab, reachable from 提醒设置.
	_check(s._tabs.get_tab_count() == 5, "settings has five tabs")
	_check(s._tabs.get_tab_title(4) == "AI 聊天", "AI 聊天 is the last tab")

	# The field is masked and its copy menu is off, so a saved key can't be read.
	_check(s._api_key_edit.secret, "key field is masked")
	_check(not s._api_key_edit.context_menu_enabled, "key field copy menu disabled")

	# Fresh start: no key, status says so.
	_check(not pet._deepseek.has_key(), "no key before saving")
	_check(s._api_key_status.text.find("尚未配置") != -1, "status shows unconfigured")

	# Save a key through the field.
	s._tabs.current_tab = 4
	s._api_key_edit.text = "sk-test-notreal-123"
	s._on_save_api_key()
	_check(pet._deepseek.has_key(), "key lands in the client")
	_check(s._api_key_edit.text == "", "field cleared after save (key hidden)")
	_check(s._api_key_status.text.find("已配置") != -1, "status shows configured")

	# The preview file carries the key; the real file is not involved.
	var preview := "user://preview_secrets_%d.json" % OS.get_process_id()
	_check(FileAccess.file_exists(preview), "preview secrets written")
	if FileAccess.file_exists(preview):
		var f := FileAccess.open(preview, FileAccess.READ)
		_check(f.get_as_text().find("sk-test-notreal-123") != -1, "key persisted to preview file")

	_finish()


func _check(cond: bool, why: String) -> void:
	if not cond:
		_fail(why)
	else:
		print("ok: ", why)


func _finish() -> void:
	print("deepseek_key finished, failures=%d" % failures)
	get_tree().quit(0 if failures == 0 else 1)


func _fail(what: String) -> void:
	failures += 1
	printerr("CHECK FAIL: ", what)
