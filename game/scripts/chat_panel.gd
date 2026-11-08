extends Panel
## Chat card: type to talk to 大肥鱼.  Owns the conversation history and its
## display; the actual DeepSeek call lives in deepseek.gd and is wired by pet.gd
## (this panel never talks to the network itself).

signal closed
signal send(messages: Array)
## Emitted when the user acknowledges the reminder shown in the banner at the
## top of the card (as opposed to `closed`, which is the ✕ on the whole card).
signal dismissed
## Emitted when the card should tuck itself back to the bubble because it has
## been idle (no hover, no typing) for COLLAPSE_IDLE seconds.  Distinct from
## `closed`: collapsing never acknowledges a pending reminder.
signal collapse

const C_PANEL := Color(0.06, 0.09, 0.17, 0.97)
const C_BORDER := Color(0.36, 0.62, 0.95, 0.55)
const C_TEXT := Color(0.88, 0.93, 1.0)
const C_DIM := Color(0.58, 0.67, 0.82)
const C_WORK := Color(0.45, 0.75, 1.0)
const C_WARN := Color(1.0, 0.78, 0.30)
## Bright yellow for a synced feed item, so it stands out from ordinary chat.
const C_FEED := Color(1.0, 0.82, 0.15)
## The bold variant of the pet's UI font, used for the feed line.
const BOLD_FONT_PATH := "C:/Windows/Fonts/msyhbd.ttc"
const C_ME := Color(0.45, 0.90, 0.62)
const C_FIELD := Color(0.10, 0.14, 0.24, 0.95)

var _font: Font
var _bold_font: FontFile
var _history: Array = []
var _log: VBoxContainer
var _scroll: ScrollContainer
var _entry: LineEdit
var _send_button: Button
var _close: Button
var _busy := false
var _idle := 0.0
var _notice_banner: Panel
var _notice_label: Label
var _notice_button: Button
var _close_ring: Control
var _ring_value := 0.0

const _BANNER_H := 46.0
const _BANNER_GAP := 6.0
## Seconds the card stays open with no hover and no typing before it collapses.
const COLLAPSE_IDLE := 5.0


func setup(font: Font) -> void:
	_font = font
	_build()
	_append("大肥鱼", "主人想和我聊什么呀？咕噜～", C_TEXT)


func focus_input() -> void:
	_entry.grab_focus()


## Auto-collapse while idle: the card stays open only while the mouse is over it
## or the user is typing.  After COLLAPSE_IDLE seconds with neither, it emits
## `collapse` so the owner can tuck it back to the bubble.
func _process(delta: float) -> void:
	if not visible:
		_idle = 0.0
		_set_ring(0.0)
		return
	if _hovering():
		_idle = 0.0
		_set_ring(0.0)
		return
	_idle += delta
	_set_ring(clampf(_idle / COLLAPSE_IDLE, 0.0, 1.0))
	if _idle >= COLLAPSE_IDLE:
		_idle = 0.0
		_set_ring(0.0)
		collapse.emit()


func _hovering() -> bool:
	# Screen-space cursor math (not get_global_mouse_position), so leaving the
	# window reads as "not hovering" instead of freezing at the last spot.
	var pointer := DisplayServer.mouse_get_position()
	var origin := DisplayServer.window_get_position()
	return get_global_rect().has_point(Vector2(pointer - origin))


func _on_entry_changed(_text: String) -> void:
	_idle = 0.0
	_set_ring(0.0)


func _set_ring(value: float) -> void:
	if is_equal_approx(value, _ring_value):
		return
	_ring_value = value
	if _close_ring != null:
		_close_ring.queue_redraw()


## A thin circular countdown around the ✕: it drains from a full ring to empty
## as the card sits idle, so the user sees how long before it folds to the bubble.
func _draw_close_ring() -> void:
	var center := _close_ring.size * 0.5
	var radius := _close_ring.size.x * 0.5 - 2.5
	_close_ring.draw_arc(center, radius, 0.0, TAU, 48, Color(1.0, 1.0, 1.0, 0.16), 2.5, true)
	var remaining := clampf(1.0 - _ring_value, 0.0, 1.0)
	if remaining > 0.001:
		_close_ring.draw_arc(center, radius, -PI * 0.5, -PI * 0.5 + remaining * TAU, 48, C_WORK, 2.5, true)


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

	var title := _label("💬 和大肥鱼聊天", 16, C_WORK)
	title.position = Vector2(14, 7)
	title.size = Vector2(240, 26)
	add_child(title)

	_close_ring = Control.new()
	_close_ring.position = Vector2(size.x - 46, 0)
	_close_ring.size = Vector2(40, 40)
	_close_ring.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_close_ring.draw.connect(_draw_close_ring)
	add_child(_close_ring)

	_close = _button("✕", 14, Vector2(28, 28))
	_close.position = Vector2(size.x - 40, 6)
	_close.pressed.connect(func(): closed.emit())
	add_child(_close)

	_build_banner()

	_scroll = ScrollContainer.new()
	_scroll.position = Vector2(10, 40)
	_scroll.size = Vector2(size.x - 20, size.y - 92)
	_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_AUTO
	add_child(_scroll)

	_log = VBoxContainer.new()
	_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	_log.add_theme_constant_override("separation", 8)
	_scroll.add_child(_log)

	_entry = _edit("和它说点什么…", 0)
	_entry.position = Vector2(10, size.y - 44)
	_entry.size = Vector2(size.x - 92, 30)
	_entry.text_submitted.connect(_on_submit)
	_entry.text_changed.connect(_on_entry_changed)
	add_child(_entry)

	_send_button = _button("发送", 13, Vector2(64, 30))
	_send_button.position = Vector2(size.x - 74, size.y - 44)
	_send_button.pressed.connect(_on_submit)
	add_child(_send_button)


func _on_submit(_text: String = "") -> void:
	if _busy:
		return
	var text: String = _entry.text.strip_edges()
	if text == "":
		return
	_entry.text = ""
	quick_send(text)


## Sends a user message directly, bypassing the panel's own entry box.  Used by
## the menu's quick-chat input (type + Enter opens the panel on this message).
func quick_send(text: String) -> void:
	if _busy:
		return
	var t := text.strip_edges()
	if t == "":
		return
	_append("我", t, C_ME)
	_history.append({"role": "user", "content": t})
	_set_busy(true)
	send.emit(_history.duplicate(true))


func reply(text: String) -> void:
	_set_busy(false)
	_history.append({"role": "assistant", "content": text})
	_append("大肥鱼", text, C_TEXT)


func error(text: String) -> void:
	_set_busy(false)
	_append("大肥鱼", text, C_WARN)


## A plain system line (logged water).  It is the pet talking at you rather than
## a chat turn, so it stays out of `_history` and is never sent to DeepSeek.
## Real reminders go through `reminder()` instead, so they are not buried here.
func notice(text: String) -> void:
	_append("大肥鱼", "🔔 " + text, C_WARN)


## A real reminder (water / sit / alarm / memo) that needs the user to act.  It
## is shown in the banner at the top of the card instead of being appended to the
## chat log, so it is never buried under the conversation when the card is open.
func reminder(text: String) -> void:
	_notice_label.text = text
	_notice_banner.visible = true
	_layout_banner()


## Hides the reminder banner (the reminder has been acknowledged or acted on).
func clear_reminder() -> void:
	_notice_banner.visible = false
	_layout_banner()


## The history scroll sits just below the title by default; when the banner is
## up it drops below the banner so the two never overlap.
func _layout_banner() -> void:
	var top := 40.0
	var height := size.y - 92.0
	if _notice_banner.visible:
		top += _BANNER_H + _BANNER_GAP
		height -= _BANNER_H + _BANNER_GAP
	_scroll.position = Vector2(10.0, top)
	_scroll.size = Vector2(size.x - 20.0, height)


func _set_busy(busy: bool) -> void:
	_busy = busy
	_entry.editable = not busy
	_send_button.disabled = busy
	_send_button.text = "…" if busy else "发送"


func _append(who: String, text: String, color: Color, bold := false) -> void:
	var label := Label.new()
	label.text = who + "：" + text
	label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	label.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	label.add_theme_font_size_override("font_size", 13)
	label.add_theme_color_override("font_color", color)
	if _font != null:
		label.add_theme_font_override("font", _bold_variant() if bold else _font)
	_log.add_child(label)
	call_deferred("_scroll_to_bottom")


## The full text of a synced feed item, shown as a yellow bold line so it stands
## out from ordinary chat and is never lost to the bubble's two-line cap.
func feed_message(text: String) -> void:
	_append("大肥鱼", "🔄 " + text, C_FEED, true)


## The bold UI font, loaded once; falls back to an emboldened variation of the
## regular font when the bold file is unavailable.
func _bold_variant() -> Font:
	if _bold_font == null:
		var loaded := FontFile.new()
		if loaded.load_dynamic_font(BOLD_FONT_PATH) == OK:
			_bold_font = loaded
	if _bold_font != null:
		return _bold_font
	var bold := FontVariation.new()
	bold.base_font = _font
	bold.variation_embolden = 0.5
	return bold


func _scroll_to_bottom() -> void:
	var bar := _scroll.get_v_scroll_bar()
	if bar != null:
		_scroll.scroll_vertical = int(bar.max_value)


# ---------------------------------------------------------------- widgets


func _label(text: String, size_px: int, color: Color) -> Label:
	var label := Label.new()
	label.text = text
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
	button.add_theme_font_size_override("font_size", size_px)
	button.add_theme_color_override("font_color", C_TEXT)
	button.add_theme_color_override("font_hover_color", Color.WHITE)
	button.add_theme_color_override("font_pressed_color", C_WORK)
	if _font != null:
		button.add_theme_font_override("font", _font)
	button.add_theme_stylebox_override("normal", _flat(C_FIELD, 6))
	button.add_theme_stylebox_override("hover", _flat(Color(0.16, 0.24, 0.38, 1.0), 6))
	button.add_theme_stylebox_override("pressed", _flat(Color(0.22, 0.34, 0.52, 1.0), 6))
	button.add_theme_stylebox_override("focus", StyleBoxEmpty.new())
	return button


func _edit(placeholder: String, width: float) -> LineEdit:
	var edit := LineEdit.new()
	edit.placeholder_text = placeholder
	if width > 0.0:
		edit.custom_minimum_size = Vector2(width, 28)
	edit.add_theme_font_size_override("font_size", 13)
	edit.add_theme_color_override("font_color", C_TEXT)
	edit.add_theme_color_override("font_placeholder_color", Color(0.58, 0.67, 0.82, 0.75))
	edit.add_theme_stylebox_override("normal", _flat(C_FIELD, 6))
	edit.add_theme_stylebox_override("focus", _flat(Color(0.16, 0.24, 0.38, 1.0), 6, C_BORDER))
	if _font != null:
		edit.add_theme_font_override("font", _font)
	return edit


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


## The reminder banner lives at the top of the card, between the title and the
## history: a warning-tinted strip with the reminder text and a single "确认"
## button that acknowledges it.  It starts hidden and only appears for a real
## reminder, so the chat log never has to carry actionable prompts.
func _build_banner() -> void:
	_notice_banner = Panel.new()
	var style := StyleBoxFlat.new()
	style.bg_color = Color(0.24, 0.18, 0.05, 0.96)
	style.border_color = C_WARN
	style.set_border_width_all(1)
	style.set_corner_radius_all(8)
	_notice_banner.add_theme_stylebox_override("panel", style)
	_notice_banner.position = Vector2(10.0, 38.0)
	_notice_banner.size = Vector2(size.x - 20.0, _BANNER_H)
	_notice_banner.visible = false
	add_child(_notice_banner)

	_notice_label = _label("", 13, C_WARN)
	_notice_label.position = Vector2(10.0, 5.0)
	_notice_label.size = Vector2(_notice_banner.size.x - 82.0, _BANNER_H - 10.0)
	_notice_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_notice_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_notice_banner.add_child(_notice_label)

	_notice_button = _button("确认", 13, Vector2(56.0, 24.0))
	_notice_button.position = Vector2(_notice_banner.size.x - 66.0, (_BANNER_H - 24.0) * 0.5)
	_notice_button.pressed.connect(func(): dismissed.emit())
	_notice_banner.add_child(_notice_button)
