extends Panel
## Reminder settings card shown over the pet: water, sitting, alarms, memos.
## Built in code so it can share the pet's CJK font and palette.

signal closed

const C_PANEL := Color(0.06, 0.09, 0.17, 0.97)
const C_BORDER := Color(0.36, 0.62, 0.95, 0.55)
const C_TEXT := Color(0.88, 0.93, 1.0)
const C_DIM := Color(0.58, 0.67, 0.82)
const C_WORK := Color(0.45, 0.75, 1.0)
const C_OK := Color(0.45, 0.90, 0.62)
const C_WARN := Color(1.0, 0.78, 0.30)
const C_FIELD := Color(0.10, 0.14, 0.24, 0.95)

const WATER_INTERVALS := [30, 45, 60, 90, 120]
const SIT_INTERVALS := [30, 45, 60, 90, 120]
const REPEATS := [["daily", "每天"], ["weekdays", "工作日"], ["once", "仅一次"]]

## How long the pet keeps the notebook up after the last keystroke.  A little
## linger so a two-second pause between words does not put the pad away; it has
## to stay longer than the pick-up/put-away clips or she would flap.
const TYPE_HOLD := 2.4

var _font: Font
var _reminders: Node
## Seconds left of "the user is writing something into a field".
var _typing := 0.0

var _tabs: TabContainer
var _water_title: Label
var _water_bar: ProgressBar
var _water_check: CheckBox
var _water_option: OptionButton
var _water_goal: SpinBox
var _sound_check: CheckBox

var _sit_title: Label
var _sit_check: CheckBox
var _sit_option: OptionButton

var _alarm_list: VBoxContainer
var _time_edit: LineEdit
var _alarm_label_edit: LineEdit
var _alarm_repeat: OptionButton

var _memo_list: VBoxContainer
var _memo_title_edit: LineEdit
var _memo_detail_edit: LineEdit
var _memo_date_edit: LineEdit

var _hint: Label
var _hint_timer := 0.0
var _loading := false
var _reload_queued := false
var _refresh_accum := 0.0


func setup(font: Font, reminders: Node) -> void:
	_font = font
	_reminders = reminders
	_build()
	_watch_typing(self)
	reload()
	_reminders.changed.connect(_on_changed)
	set_process(true)


## True while the user is writing into one of the card's fields, so the pet can
## hold the notebook and jot it down (`_note_taking` in pet.gd).
func is_typing() -> bool:
	return visible and _typing > 0.0


## Every text field (memo, alarm label and time, the water goal's spin box)
## feeds the same "she is writing" timer.
func _watch_typing(node: Node) -> void:
	if node is LineEdit:
		var edit := node as LineEdit
		edit.text_changed.connect(func(_text: String): _note_typing())
		edit.focus_entered.connect(_note_typing)
	for child in node.get_children():
		_watch_typing(child)


func _note_typing() -> void:
	_typing = TYPE_HOLD


func _build() -> void:
	z_index = 20
	var style := StyleBoxFlat.new()
	style.bg_color = C_PANEL
	style.border_color = C_BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(14)
	style.shadow_color = Color(0, 0, 0, 0.5)
	style.shadow_size = 12
	add_theme_stylebox_override("panel", style)

	var title := _label("⏰ 提醒设置", 16, C_WORK)
	title.position = Vector2(14, 7)
	title.size = Vector2(220, 26)
	add_child(title)

	var close := _button("✕", 14, Vector2(32, 26))
	close.position = Vector2(size.x - 44, 7)
	close.pressed.connect(func(): closed.emit())
	add_child(close)

	_tabs = TabContainer.new()
	_tabs.position = Vector2(8, 38)
	_tabs.size = size - Vector2(16, 62)
	_tabs.add_theme_font_override("font", _font)
	_tabs.add_theme_font_size_override("font_size", 13)
	_tabs.add_theme_color_override("font_selected_color", C_TEXT)
	_tabs.add_theme_color_override("font_unselected_color", C_DIM)
	add_child(_tabs)

	_build_water(_tab("喝水"))
	_build_sit(_tab("久坐"))
	_build_alarm(_tab("闹钟"))
	_build_memo(_tab("备忘"))

	_hint = _label("", 12, C_WARN)
	_hint.position = Vector2(14, size.y - 20)
	_hint.size = Vector2(size.x - 28, 16)
	_hint.visible = false
	add_child(_hint)


func _tab(tab_name: String) -> VBoxContainer:
	var scroll := ScrollContainer.new()
	scroll.name = tab_name
	scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	var box := VBoxContainer.new()
	box.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_theme_constant_override("separation", 8)
	scroll.add_child(box)
	_tabs.add_child(scroll)
	_tabs.set_tab_title(_tabs.get_tab_count() - 1, tab_name)
	return box


# ---------------------------------------------------------------- tabs


func _build_water(box: VBoxContainer) -> void:
	_water_title = _label("今天 0 / 1500 ml", 14, C_TEXT)
	box.add_child(_water_title)

	_water_bar = ProgressBar.new()
	_water_bar.custom_minimum_size = Vector2(0, 10)
	_water_bar.show_percentage = false
	_water_bar.max_value = 1500
	_water_bar.add_theme_stylebox_override("background", _flat(C_FIELD, 5))
	_water_bar.add_theme_stylebox_override("fill", _flat(Color(0.35, 0.66, 1.0), 5))
	box.add_child(_water_bar)

	box.add_child(_label("点一杯，大肥鱼陪你一起喝", 12, C_DIM))

	var cups := _row(box)
	for entry in [[100, "一口 100"], [250, "一杯 250"], [500, "大杯 500"]]:
		var button := _button(entry[1], 13, Vector2(0, 32))
		button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		button.pressed.connect(_on_water_button.bind(entry[0]))
		cups.add_child(button)

	var remind := _row(box)
	_water_check = _check("按时提醒")
	_water_check.toggled.connect(func(on): _setter("water_enabled", on))
	remind.add_child(_water_check)
	remind.add_child(_spacer())
	_water_option = _option(["30 分钟", "45 分钟", "60 分钟", "90 分钟", "120 分钟"], WATER_INTERVALS)
	_water_option.item_selected.connect(func(i): _setter("water_interval", WATER_INTERVALS[i]))
	remind.add_child(_water_option)
	remind.add_child(_label("一次", 12, C_DIM))

	var goal := _row(box)
	goal.add_child(_label("每日目标", 13, C_TEXT))
	goal.add_child(_spacer())
	_water_goal = SpinBox.new()
	_water_goal.min_value = 300
	_water_goal.max_value = 6000
	_water_goal.step = 100
	_water_goal.custom_minimum_size = Vector2(96, 26)
	var goal_edit := _water_goal.get_line_edit()
	goal_edit.add_theme_font_size_override("font_size", 13)
	goal_edit.add_theme_color_override("font_color", C_TEXT)
	if _font != null:
		goal_edit.add_theme_font_override("font", _font)
	_water_goal.value_changed.connect(func(v): _setter("goal", int(v)))
	goal.add_child(_water_goal)
	goal.add_child(_label("ml", 12, C_DIM))

	var extra := _row(box)
	_sound_check = _check("提示音")
	_sound_check.toggled.connect(func(on): _setter("sound", on))
	extra.add_child(_sound_check)
	extra.add_child(_spacer())
	var reset := _button("清零今日", 12, Vector2(84, 26))
	reset.pressed.connect(func(): _reminders.reset_water_day())
	extra.add_child(reset)


func _build_sit(box: VBoxContainer) -> void:
	_sit_title = _label("已连续坐 0 分钟", 14, C_TEXT)
	box.add_child(_sit_title)
	box.add_child(_label("每小时提醒你站起来动一动，和大肥鱼一起伸个懒腰", 12, C_DIM))

	var on_row := _row(box)
	_sit_check = _check("开启久坐提醒")
	_sit_check.toggled.connect(func(on): _setter("sit_enabled", on))
	on_row.add_child(_sit_check)

	var every := _row(box)
	every.add_child(_label("每", 13, C_TEXT))
	_sit_option = _option(["30 分钟", "45 分钟", "60 分钟", "90 分钟", "120 分钟"], SIT_INTERVALS)
	_sit_option.item_selected.connect(func(i): _setter("sit_interval", SIT_INTERVALS[i]))
	every.add_child(_sit_option)
	every.add_child(_label("提醒一次", 13, C_TEXT))

	var stand := _button("我起来活动了", 14, Vector2(0, 34))
	stand.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	stand.pressed.connect(func():
		_reminders.stand_up()
		_show_hint("计时已重置，继续保持～", C_OK))
	box.add_child(stand)


func _build_alarm(box: VBoxContainer) -> void:
	box.add_child(_label("到点提醒，大肥鱼会跳起来叫你", 12, C_DIM))

	var add_row := _row(box)
	_time_edit = _edit("09:30", 78)
	add_row.add_child(_time_edit)
	_alarm_label_edit = _edit("备注（可空）", 0)
	_alarm_label_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	add_row.add_child(_alarm_label_edit)
	var add := _button("添加", 13, Vector2(52, 28))
	add.pressed.connect(_on_add_alarm)
	add_row.add_child(add)
	_alarm_label_edit.text_submitted.connect(func(_text): _on_add_alarm())

	var repeat_row := _row(box)
	repeat_row.add_child(_label("重复", 12, C_DIM))
	_alarm_repeat = _option(["每天", "工作日", "仅一次"], [])
	for i in REPEATS.size():
		_alarm_repeat.set_item_metadata(i, REPEATS[i][0])
	repeat_row.add_child(_alarm_repeat)
	repeat_row.add_child(_spacer())

	box.add_child(HSeparator.new())
	_alarm_list = VBoxContainer.new()
	_alarm_list.add_theme_constant_override("separation", 4)
	box.add_child(_alarm_list)


func _build_memo(box: VBoxContainer) -> void:
	box.add_child(_label("写下要做的事，指定的那天会提醒你", 12, C_DIM))

	_memo_title_edit = _edit("标题（必填）", 0)
	_memo_title_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(_memo_title_edit)

	_memo_detail_edit = _edit("详细内容（可空）", 0)
	_memo_detail_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	box.add_child(_memo_detail_edit)

	var date_row := _row(box)
	_memo_date_edit = _edit("日期 YYYY-MM-DD（可空）", 0)
	_memo_date_edit.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	date_row.add_child(_memo_date_edit)
	var add := _button("添加", 13, Vector2(52, 28))
	add.pressed.connect(_on_add_memo)
	date_row.add_child(add)
	_memo_date_edit.text_submitted.connect(func(_text): _on_add_memo())

	box.add_child(HSeparator.new())
	_memo_list = VBoxContainer.new()
	_memo_list.add_theme_constant_override("separation", 4)
	box.add_child(_memo_list)


# ---------------------------------------------------------------- actions


func _on_water_button(ml: int) -> void:
	_reminders.log_water(ml)


func _on_add_alarm() -> void:
	var repeat := str(_alarm_repeat.get_item_metadata(_alarm_repeat.selected))
	if not _reminders.add_alarm(_time_edit.text, _alarm_label_edit.text, repeat):
		_show_hint("时间格式要像 09:30 这样", C_WARN)
		return
	_time_edit.text = ""
	_alarm_label_edit.text = ""
	_show_hint("闹钟已添加", C_OK)


func _on_add_memo() -> void:
	if not _reminders.add_memo(_memo_title_edit.text, _memo_detail_edit.text, _memo_date_edit.text):
		_show_hint("标题不能为空，日期格式 YYYY-MM-DD", C_WARN)
		return
	_memo_title_edit.text = ""
	_memo_detail_edit.text = ""
	_memo_date_edit.text = ""
	_show_hint("备忘已添加", C_OK)


func _setter(kind: String, value) -> void:
	if _loading:
		return
	match kind:
		"water_enabled":
			_reminders.set_water_enabled(value)
		"water_interval":
			_reminders.set_water_interval(value)
		"goal":
			_reminders.set_goal(value)
		"sit_enabled":
			_reminders.set_sit_enabled(value)
		"sit_interval":
			_reminders.set_sit_interval(value)
		"sound":
			_reminders.set_sound(value)


func _show_hint(text: String, color: Color) -> void:
	_hint.text = text
	_hint.add_theme_color_override("font_color", color)
	_hint.visible = true
	_hint_timer = 2.5


# ---------------------------------------------------------------- refresh


func reload() -> void:
	_loading = true
	_water_title.text = "今天 %d / %d ml" % [_reminders.today_ml(), _reminders.goal_ml()]
	_water_bar.max_value = _reminders.goal_ml()
	_water_bar.value = _reminders.today_ml()
	_water_check.set_pressed_no_signal(_reminders.water_enabled())
	_water_option.select(_index_of(WATER_INTERVALS, _reminders.water_interval()))
	_water_goal.set_value_no_signal(_reminders.goal_ml())
	_sound_check.set_pressed_no_signal(_reminders.sound_on())

	_sit_check.set_pressed_no_signal(_reminders.sit_enabled())
	_sit_option.select(_index_of(SIT_INTERVALS, _reminders.sit_interval()))
	_update_sit_label()

	_rebuild_alarms()
	_rebuild_memos()
	_loading = false


func _update_sit_label() -> void:
	var minutes: int = int(_reminders.sit_minutes())
	_sit_title.text = "已连续坐 %d 分钟" % minutes
	if minutes >= 90:
		_sit_title.add_theme_color_override("font_color", C_WARN)
	else:
		_sit_title.add_theme_color_override("font_color", C_TEXT)


func _rebuild_alarms() -> void:
	for child in _alarm_list.get_children():
		_alarm_list.remove_child(child)
		child.queue_free()
	var items: Array = _reminders.alarms()
	if items.is_empty():
		_alarm_list.add_child(_label("还没有闹钟", 12, C_DIM))
		return
	for alarm in items:
		var row := _row(_alarm_list)
		var on := bool(alarm.get("on", true))
		var text := "%s  %s" % [str(alarm.get("time", "")), str(alarm.get("label", ""))]
		var check := _check(text.strip_edges(), 13)
		check.set_pressed_no_signal(on)
		check.add_theme_color_override("font_color", C_TEXT if on else C_DIM)
		check.toggled.connect(func(_state): _reminders.toggle_alarm(str(alarm.get("id", ""))))
		check.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(check)
		var del := _button("删", 12, Vector2(38, 24))
		del.pressed.connect(func(): _reminders.remove_alarm(str(alarm.get("id", ""))))
		row.add_child(del)


func _rebuild_memos() -> void:
	for child in _memo_list.get_children():
		_memo_list.remove_child(child)
		child.queue_free()
	var items: Array = _reminders.memos()
	if items.is_empty():
		_memo_list.add_child(_label("还没有备忘", 12, C_DIM))
		return
	for memo in items:
		var done := bool(memo.get("done", false))
		var date := str(memo.get("date", ""))
		var head := "✓ " if done else "• "
		var text := head + str(memo.get("title", ""))
		if date != "":
			text += "   " + date
		var row := _row(_memo_list)
		var check := _check(text, 13)
		check.set_pressed_no_signal(done)
		check.add_theme_color_override("font_color", C_DIM if done else C_TEXT)
		check.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		check.toggled.connect(func(_state): _reminders.toggle_memo(str(memo.get("id", ""))))
		row.add_child(check)
		var del := _button("删", 12, Vector2(38, 24))
		del.pressed.connect(func(): _reminders.remove_memo(str(memo.get("id", ""))))
		row.add_child(del)


func _on_changed() -> void:
	if not visible or _reload_queued:
		return
	_reload_queued = true
	call_deferred("_deferred_reload")


func _deferred_reload() -> void:
	_reload_queued = false
	if visible:
		reload()


func _process(delta: float) -> void:
	if _typing > 0.0:
		_typing = maxf(0.0, _typing - delta)
	if _hint_timer > 0.0:
		_hint_timer -= delta
		if _hint_timer <= 0.0:
			_hint.visible = false
	if not visible:
		# a closed card is not being written into, whatever the timer says
		_typing = 0.0
		return
	_refresh_accum += delta
	if _refresh_accum < 1.0:
		return
	_refresh_accum = 0.0
	_update_sit_label()
	_water_title.text = "今天 %d / %d ml" % [_reminders.today_ml(), _reminders.goal_ml()]
	_water_bar.value = _reminders.today_ml()


func _index_of(values: Array, value: int) -> int:
	var idx := values.find(value)
	return idx if idx >= 0 else 0


# ---------------------------------------------------------------- widgets


func _row(parent: Control) -> HBoxContainer:
	var row := HBoxContainer.new()
	row.add_theme_constant_override("separation", 6)
	parent.add_child(row)
	return row


func _spacer() -> Control:
	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	return spacer


func _label(text: String, size_px: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
	# No overrun trimming: any TRIM_* mode reports a 1 px minimum width, and
	# inside an HBox with a spacer that collapses the label to nothing.
	label.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	label.add_theme_font_size_override("font_size", size_px)
	label.add_theme_color_override("font_color", color)
	if _font != null:
		label.add_theme_font_override("font", _font)
	return label


func _button(text: String, size_px: int, min_size: Vector2) -> Button:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = min_size
	_style_text_control(button, size_px)
	return button


func _check(text: String, size_px: int = 13) -> CheckBox:
	var check := CheckBox.new()
	check.text = text
	check.focus_mode = Control.FOCUS_NONE
	check.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	_style_text_control(check, size_px)
	return check


func _option(items: Array, values: Array) -> OptionButton:
	var option := OptionButton.new()
	for i in items.size():
		option.add_item(items[i])
		if not values.is_empty():
			option.set_item_metadata(i, values[i])
	option.custom_minimum_size = Vector2(92, 26)
	_style_text_control(option, 12)
	return option


func _edit(placeholder: String, width: float) -> LineEdit:
	var edit := LineEdit.new()
	edit.placeholder_text = placeholder
	edit.custom_minimum_size = Vector2(width, 28)
	edit.size_flags_vertical = Control.SIZE_SHRINK_CENTER
	edit.add_theme_font_size_override("font_size", 13)
	edit.add_theme_color_override("font_color", C_TEXT)
	edit.add_theme_color_override("font_placeholder_color", Color(0.58, 0.67, 0.82, 0.75))
	edit.add_theme_stylebox_override("normal", _flat(C_FIELD, 6))
	edit.add_theme_stylebox_override("focus", _flat(Color(0.16, 0.24, 0.38, 1.0), 6, C_BORDER))
	if _font != null:
		edit.add_theme_font_override("font", _font)
	return edit


func _style_text_control(control: Control, size_px: int) -> void:
	control.add_theme_font_size_override("font_size", size_px)
	control.add_theme_color_override("font_color", C_TEXT)
	control.add_theme_color_override("font_hover_color", Color.WHITE)
	control.add_theme_color_override("font_pressed_color", C_WORK)
	if _font != null:
		control.add_theme_font_override("font", _font)
	if control is Button and not control is CheckBox:
		control.add_theme_stylebox_override("normal", _flat(C_FIELD, 6))
		control.add_theme_stylebox_override("hover", _flat(Color(0.16, 0.24, 0.38, 1.0), 6))
		control.add_theme_stylebox_override("pressed", _flat(Color(0.22, 0.34, 0.52, 1.0), 6))
		control.add_theme_stylebox_override("focus", StyleBoxEmpty.new())


func _flat(color: Color, radius: int, border: Color = Color(0, 0, 0, 0)) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = color
	style.set_corner_radius_all(radius)
	style.content_margin_left = 8
	style.content_margin_right = 8
	style.content_margin_top = 3
	style.content_margin_bottom = 3
	if border.a > 0.0:
		style.border_color = border
		style.set_border_width_all(1)
	return style
