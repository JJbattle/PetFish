extends Node
## Logic test for the reminder engine.  Runs against a throwaway profile in
## tools/_debug so the real data/pet_data.json is never touched.
##
## Run:  Godot --path game res://tests/reminders_test.tscn

const Reminders = preload("res://scripts/reminders.gd")
const TEST_DATA := "I:/PetFish/tools/_debug/reminders_test.json"

var _notices: Array = []
var _fail := 0


func _ready() -> void:
	DirAccess.remove_absolute(TEST_DATA)

	var r = Reminders.new()
	r.data_path = TEST_DATA
	add_child(r)
	r.set_process(false)
	r.notice.connect(func(kind, text): _notices.append([kind, text]))

	# --- water
	_notices.clear()
	r.log_water(250)
	_check(r.today_ml() == 250, "喝水记 250 ml")
	r._data["water"]["last_remind"] = Time.get_unix_time_from_system() - 61 * 60
	r._update()
	_check(_has("water"), "一小时没喝水会提醒")
	_check(_text("water").contains("还差"), "喝水提醒里带剩余量")

	# --- sitting
	_notices.clear()
	r._data["sit"]["since"] = Time.get_unix_time_from_system() - 61 * 60
	r._update()
	_check(_has("sit"), "坐满一小时会提醒")
	_check(_text("sit") == "坐了1小时啦，起来伸个懒腰", "久坐提示文案")
	r.stand_up()
	_check(r.sit_minutes() == 0, "站起来后计时归零")

	# --- alarms
	var dt := Time.get_datetime_dict_from_system()
	var hm := "%02d:%02d" % [int(dt["hour"]), int(dt["minute"])]
	_notices.clear()
	_check(r.add_alarm(hm, "测试", "once"), "添加闹钟")
	r._update()
	_check(_has("alarm"), "到点闹钟会响")
	_notices.clear()
	r._update()
	_check(not _has("alarm"), "一次性闹钟不重复")
	_check(not bool(r.alarms()[0].get("on", true)), "一次性闹钟自动关闭")

	# --- memos
	_check(r.add_memo("交房租", "1000 元", Time.get_date_string_from_system()), "添加当天备忘")
	_notices.clear()
	r._update()
	_check(_has("memo"), "当天备忘会提醒")
	_check(_text("memo").contains("交房租"), "备忘提醒里带标题")
	_notices.clear()
	r._update()
	_check(not _has("memo"), "同一天只提醒一次")
	r.toggle_memo(str(r.memos()[0]["id"]))
	_check(bool(r.memos()[0]["done"]), "备忘可勾选完成")

	# --- input validation
	_check(not r.add_alarm("25:00", "", "daily"), "拒绝非法时间")
	_check(not r.add_memo("", "", ""), "拒绝空标题")
	_check(not r.add_memo("x", "", "2026-13-01"), "拒绝非法日期")

	# --- persistence
	var r2 = Reminders.new()
	r2.data_path = TEST_DATA
	add_child(r2)
	r2.set_process(false)
	_check(r2.today_ml() == 250, "喝水记录已持久化")
	_check(r2.memos().size() == 1, "备忘已持久化")
	_check(r2.alarms().size() == 1, "闹钟已持久化")

	print("reminders_test: failures=", _fail)
	get_tree().quit(1 if _fail > 0 else 0)


func _check(ok: bool, what: String) -> void:
	if ok:
		print("PASS  ", what)
	else:
		_fail += 1
		print("FAIL  ", what)


func _has(kind: String) -> bool:
	for item in _notices:
		if item[0] == kind:
			return true
	return false


func _text(kind: String) -> String:
	for item in _notices:
		if item[0] == kind:
			return str(item[1])
	return ""
