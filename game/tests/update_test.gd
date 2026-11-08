extends Node
## Logic test for the app updater (updater.gd).  Network-free: it drives
## _is_newer / _decide and the non-download branches of _on_manifest_done
## directly, so the harness never reaches the network.

const Updater = preload("res://scripts/updater.gd")

var _fail := 0


func _ready() -> void:
	var u = Updater.new()
	add_child(u)

	# --- version compare (plain x.y.z, leading v ignored, missing segments = 0)
	_check(u._is_newer("0.1.10", "0.1.9"), "0.1.10 新于 0.1.9")
	_check(u._is_newer("0.2.0", "0.1.9"), "0.2.0 新于 0.1.9")
	_check(u._is_newer("v0.2.0", "0.1.9"), "v 前缀忽略")
	_check(not u._is_newer("0.1.9", "0.1.9"), "相同版本不新")
	_check(not u._is_newer("0.1.8", "0.1.9"), "旧版本不新")
	_check(u._is_newer("1.0", "0.9.9"), "缺段按 0 补")
	_check(not u._is_newer("0.1.0", "0.1.0.1"), "更长旧段不新")

	# --- _decide
	var bad := u._decide("not json")
	_check(bad.error != "", "坏 JSON 报错")
	var missing := u._decide('{"url":"x"}')
	_check(missing.error != "", "缺 version 报错")
	var same := u._decide('{"version":"0.1.0","url":"","notes":""}')
	_check(not same.newer and same.error == "", "同版本 newer=false")
	var older := u._decide('{"version":"0.0.9","url":"http://x/FishPet.exe"}')
	_check(not older.newer, "旧版本 newer=false")
	var newer := u._decide('{"version":"0.2.0","url":"http://x/FishPet.exe","notes":"hi"}')
	_check(newer.newer and newer.version == "0.2.0" and newer.url == "http://x/FishPet.exe"
		and newer.notes == "hi", "新版本透传 version/url/notes")

	# --- _on_manifest_done 非下载分支
	var checked: Array = []
	u.update_checked.connect(func(msg): checked.append(msg))

	u._manual = true
	u._on_manifest_done(HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray())
	_check(checked.size() == 1 and checked[0] == "更新检查失败，请稍后再试", "网络失败提示重试")
	_check(not u._manual, "失败后清除 manual")

	u._manual = true
	u._on_manifest_done(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(),
		'{"version":"0.1.0"}'.to_utf8_buffer())
	_check(checked.size() == 2 and checked[1] == "已经是最新版本", "同版本提示已最新")
	_check(not u._manual, "已最新后清除 manual")

	u._manual = true
	u._on_manifest_done(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(),
		'{"version":"0.2.0","url":""}'.to_utf8_buffer())
	_check(checked.size() == 3 and checked[2] == "发现新版本 v0.2.0，安装包尚未发布",
		"新版本无安装包提示")

	print("update_test: failures=", _fail)
	get_tree().quit(1 if _fail > 0 else 0)


func _check(ok: bool, what: String) -> void:
	if ok:
		print("PASS  ", what)
	else:
		_fail += 1
		print("FAIL  ", what)
