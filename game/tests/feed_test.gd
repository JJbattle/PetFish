extends Node
## Logic test for the weekly feed engine (git_feed.gd).  Network-free: it drives
## `_ingest` directly and checks the Monday naming, dedupe and persistence.
##
## Run:  Godot --path game res://tests/feed_test.tscn

const GitFeed = preload("res://scripts/git_feed.gd")
const TEST_DATA := "I:/PetFish/tools/_debug/feed_test.json"

var _fail := 0


func _ready() -> void:
	DirAccess.remove_absolute(TEST_DATA)

	var f = GitFeed.new()
	f.data_path = TEST_DATA
	add_child(f)
	f.set_process(false)

	# --- week_monday naming
	var monday := f.week_monday()
	_check(_date_ok(monday), "week_monday 是 YYYY-MM-DD: " + monday)
	_check(_is_monday(monday), "week_monday 落在周一")
	_check(_within_week(monday), "week_monday 是本周")

	# --- ingest: emit / dedupe / blank / new
	var seen: Array = []
	f.feed_ready.connect(func(text): seen.append(text))
	f._ingest("你好，第一条")
	_check(seen.size() == 1, "首次内容触发 feed_ready")
	f._ingest("你好，第一条")
	_check(seen.size() == 1, "相同内容不重复触发")
	f._ingest("   \n  ")
	_check(seen.size() == 1, "空内容忽略")
	f._ingest("第二条更新")
	_check(seen.size() == 2, "新内容再次触发")
	_check(seen.size() == 2 and str(seen[1]) == "第二条更新", "内容原文透传")

	# --- persistence: a second instance resumes from the saved hash
	var f2 = GitFeed.new()
	f2.data_path = TEST_DATA
	add_child(f2)
	f2.set_process(false)
	var seen2: Array = []
	f2.feed_ready.connect(func(text): seen2.append(text))
	f2._ingest("第二条更新")
	_check(seen2.size() == 0, "重启后相同内容不重复触发")
	f2._ingest("第三条")
	_check(seen2.size() == 1, "重启后新内容触发")

	# --- manual check (menu "检查更新"): feed_checked reports nothing-new / 404 /
	# error, and stays silent for genuinely new content (feed_ready covers that).
	var checked: Array = []
	f2.feed_checked.connect(func(msg): checked.append(msg))

	f2._manual = true
	f2._on_done(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), "第三条".to_utf8_buffer())
	_check(checked.size() == 1 and checked[0] == "没有可同步的新内容",
		"手动检查命中旧内容提示没有新内容")
	_check(not f2._manual, "手动标记在结果后清除")

	f2._manual = true
	f2._on_done(HTTPRequest.RESULT_SUCCESS, 404, PackedStringArray(), PackedByteArray())
	_check(checked.size() == 2 and checked[1] == "这周还没有新内容", "404 提示本周无内容")

	f2._manual = true
	f2._on_done(HTTPRequest.RESULT_TIMEOUT, 0, PackedStringArray(), PackedByteArray())
	_check(checked.size() == 3 and checked[2] == "更新失败，请稍后再试", "网络失败提示重试")

	var new_before := seen2.size()
	f2._manual = true
	f2._on_done(HTTPRequest.RESULT_SUCCESS, 200, PackedStringArray(), "第四条".to_utf8_buffer())
	_check(seen2.size() == new_before + 1, "手动检查命中新内容触发 feed_ready")
	_check(checked.size() == 3, "手动检查命中新内容不再提示 feed_checked")
	_check(not f2._manual, "手动标记在新内容后清除")

	print("feed_test: failures=", _fail)
	get_tree().quit(1 if _fail > 0 else 0)


func _check(ok: bool, what: String) -> void:
	if ok:
		print("PASS  ", what)
	else:
		_fail += 1
		print("FAIL  ", what)


func _date_ok(s: String) -> bool:
	var p := s.split("-")
	return p.size() == 3 and p[0].is_valid_int() and p[1].is_valid_int() and p[2].is_valid_int()


func _is_monday(s: String) -> bool:
	var p := s.split("-")
	if p.size() != 3:
		return false
	var ts := Time.get_unix_time_from_datetime_dict({
		"year": int(p[0]), "month": int(p[1]), "day": int(p[2]),
		"hour": 0, "minute": 0, "second": 0})
	return (int(ts / 86400.0) + 4) % 7 == 1


func _within_week(s: String) -> bool:
	var p := s.split("-")
	if p.size() != 3:
		return false
	var monday_ts := Time.get_unix_time_from_datetime_dict({
		"year": int(p[0]), "month": int(p[1]), "day": int(p[2]),
		"hour": 0, "minute": 0, "second": 0})
	var now := Time.get_unix_time_from_system()
	return monday_ts <= now and now < monday_ts + 7 * 86400
