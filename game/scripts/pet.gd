extends Control
## Fishpet: a borderless, always-on-top, per-pixel-transparent overlay that
## shows what the local Claude Code sessions are doing.
##
## Data flow: hook.py writes one small JSON per session -> this script polls
## that directory twice a second and tails the transcript for the current tool.

const StatusStore = preload("res://scripts/status_store.gd")
const TranscriptTail = preload("res://scripts/transcript_tail.gd")
const Silhouette = preload("res://scripts/silhouette.gd")

const STATE_DIR := "I:/PetFish/state"
const CONFIG_PATH := "I:/PetFish/window.json"
const FONT_PATH := "C:/Windows/Fonts/msyh.ttc"
const PET_TEXTURE_PATH := "res://assets/pet.png"

const WIN_SIZE := Vector2(380, 480)
const PET_TARGET_H := 284.0
const PET_BOTTOM := 474.0
const POLL_INTERVAL := 0.5
const HOVER_GRACE := 0.25

const C_PANEL := Color(0.06, 0.09, 0.17, 0.94)
const C_BORDER := Color(0.36, 0.62, 0.95, 0.55)
const C_TEXT := Color(0.88, 0.93, 1.0)
const C_DIM := Color(0.58, 0.67, 0.82)
const C_WORK := Color(0.45, 0.75, 1.0)
const C_WARN := Color(1.0, 0.78, 0.30)
const C_OK := Color(0.45, 0.90, 0.62)

var _font: Font
var _pet: TextureRect
var _pet_image: Image
var _pet_base_pos := Vector2.ZERO
var _pet_rect := Rect2()

var _bubble: Panel
var _bubble_label: Label
var _bubble_rect := Rect2(16, 14, 348, 52)

var _panel: Panel
var _state_label: Label
var _action_label: Label
var _stats_label: Label
var _project_label: Label
var _panel_rect := Rect2(16, 76, 348, 112)

var _menu: Panel
var _menu_rect := Rect2()
var _menu_open := false

var _store
var _tail

var _entry: Dictionary = {}
var _state := "idle"
var _state_age := 0.0
var _done_timer := 0.0
var _t := 0.0
var _poll_accum := 0.0
var _save_accum := 0.0
var _hover := false
var _hover_hold := 0.0
var _pinned_id := ""
var _last_saved_pos := Vector2i(99999, 99999)
var _passthrough_key := ""


func _ready() -> void:
	_setup_window()
	_load_font()
	_load_pet()
	_build_ui()
	_store = StatusStore.new(STATE_DIR)
	_tail = TranscriptTail.new()
	_load_config()
	_refresh_status()
	_update_passthrough()


func _setup_window() -> void:
	var win := get_window()
	win.borderless = true
	win.always_on_top = true
	win.transparent = true
	win.size = Vector2i(WIN_SIZE)
	win.min_size = Vector2i(WIN_SIZE)
	win.max_size = Vector2i(WIN_SIZE)
	get_viewport().transparent_bg = true
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, true)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, true)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT, true)
	mouse_filter = Control.MOUSE_FILTER_IGNORE


func _load_font() -> void:
	var font_file := FontFile.new()
	if font_file.load_dynamic_font(FONT_PATH) == OK:
		_font = font_file
	else:
		_font = ThemeDB.fallback_font


func _load_pet() -> void:
	_pet = TextureRect.new()
	_pet.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_pet.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	_pet.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	if ResourceLoader.exists(PET_TEXTURE_PATH):
		_pet.texture = load(PET_TEXTURE_PATH)
	if _pet.texture == null:
		# Placeholder so the overlay is still usable before the artwork exists.
		_pet_image = Image.create(128, 160, false, Image.FORMAT_RGBA8)
		_pet_image.fill(Color(0.30, 0.55, 0.95, 0.9))
		_pet.texture = ImageTexture.create_from_image(_pet_image)
	else:
		_pet_image = _pet.texture.get_image()

	var tex_size := _pet.texture.get_size()
	var ratio := PET_TARGET_H / maxf(1.0, tex_size.y)
	var draw_size := tex_size * ratio
	_pet.size = draw_size
	_pet.position = Vector2((WIN_SIZE.x - draw_size.x) * 0.5, PET_BOTTOM - draw_size.y)
	_pet.pivot_offset = Vector2(draw_size.x * 0.5, draw_size.y)
	_pet_base_pos = _pet.position
	_pet_rect = Rect2(_pet.position, draw_size)
	add_child(_pet)


func _build_ui() -> void:
	# Plain Panel + absolutely placed Labels: Panel never re-lays out its
	# children, so sizes stay exactly what we ask for.
	_bubble = _make_panel(_bubble_rect)
	_bubble_label = _place_label(_bubble, Vector2(13.0, 7.0), _bubble_rect.size - Vector2(26.0, 14.0), 15, C_TEXT)
	_bubble_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bubble_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	_bubble_label.text = "打盹中…"
	add_child(_bubble)

	_panel = _make_panel(_panel_rect)
	_panel.visible = false
	_state_label = _place_label(_panel, Vector2(13.0, 8.0), Vector2(322.0, 24.0), 16, C_WORK)
	_action_label = _place_label(_panel, Vector2(13.0, 34.0), Vector2(322.0, 22.0), 14, C_TEXT)
	_stats_label = _place_label(_panel, Vector2(13.0, 58.0), Vector2(322.0, 20.0), 13, C_DIM)
	_project_label = _place_label(_panel, Vector2(13.0, 80.0), Vector2(322.0, 20.0), 12, C_DIM)
	add_child(_panel)

	_menu = _make_panel(Rect2(Vector2.ZERO, Vector2(150, 118)))
	_menu.visible = false
	var menu_box := VBoxContainer.new()
	menu_box.position = Vector2(12.0, 9.0)
	menu_box.size = Vector2(126.0, 100.0)
	menu_box.add_theme_constant_override("separation", 4)
	_menu.add_child(menu_box)
	for item in [["退出", "quit"], ["切换会话", "cycle"], ["取消固定", "unpin"]]:
		var button := Button.new()
		button.text = item[0]
		button.focus_mode = Control.FOCUS_NONE
		button.custom_minimum_size = Vector2(126, 30)
		if _font != null:
			button.add_theme_font_override("font", _font)
			button.add_theme_font_size_override("font_size", 14)
		button.pressed.connect(_on_menu_action.bind(item[1]))
		menu_box.add_child(button)
	add_child(_menu)


func _make_panel(rect: Rect2) -> Panel:
	var panel := Panel.new()
	panel.position = rect.position
	panel.size = rect.size
	var style := StyleBoxFlat.new()
	style.bg_color = C_PANEL
	style.border_color = C_BORDER
	style.set_border_width_all(1)
	style.set_corner_radius_all(14)
	style.shadow_color = Color(0, 0, 0, 0.42)
	style.shadow_size = 8
	panel.add_theme_stylebox_override("panel", style)
	return panel


func _place_label(parent: Control, at: Vector2, area: Vector2, size_px: int, color: Color) -> Label:
	var label := _make_label(size_px, color)
	label.position = at
	label.size = area
	parent.add_child(label)
	return label


func _make_label(size_px: int, color: Color) -> Label:
	var label := Label.new()
	label.autowrap_mode = TextServer.AUTOWRAP_OFF
	label.clip_text = true
	label.text_overrun_behavior = TextServer.OVERRUN_TRIM_ELLIPSIS
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", size_px)
	label.add_theme_color_override("font_color", color)
	if _font != null:
		label.add_theme_font_override("font", _font)
	return label


# ---------------------------------------------------------------- status


func _process(delta: float) -> void:
	_t += delta
	_state_age += delta
	if _done_timer > 0.0:
		_done_timer -= delta
	_poll_accum += delta
	if _poll_accum >= POLL_INTERVAL:
		_poll_accum = 0.0
		_refresh_status()
	_update_hover(delta)
	_animate()
	_maybe_save_position(delta)


func _refresh_status() -> void:
	var entry: Dictionary = _store.best(_pinned_id)
	if entry.is_empty():
		_entry = {}
		_tail.set_path("")
		_set_state("idle")
		_refresh_texts()
		return
	_entry = entry
	_tail.set_path(str(entry.get("transcript_path", "")))
	_tail.poll()

	var state: String = _store.effective_state(entry)
	# Approving a permission prompt fires no hook - detect resumed work instead.
	if state == "needs_input" and _tail.last_tool_unix > _num(entry, "ts") + 0.5:
		state = "working"
	_set_state(state)
	_refresh_texts()


func _set_state(next_state: String) -> void:
	if next_state == _state:
		return
	_state = next_state
	_state_age = 0.0
	if _state == "done":
		_done_timer = 1.4
	queue_redraw()


func _refresh_texts() -> void:
	var action := _current_action()
	var elapsed := _elapsed()
	var title := _state_title()

	_state_label.text = "● " + title
	_state_label.add_theme_color_override("font_color", _state_color())
	_action_label.text = "动作  " + (action if action != "" else "…")
	_stats_label.text = "已用 %s   ·   工具 ×%d" % [_fmt_time(elapsed), _tail.tool_count]
	var project := str(_entry.get("project", ""))
	var branch_hint := project if project != "" else "无会话"
	_project_label.text = "%s   ·   %s" % [branch_hint, _tail.tool_name if _tail.tool_name != "" else "—"]

	match _state:
		"working":
			_bubble_label.text = action if action != "" else "思考中…"
		"needs_input":
			_bubble_label.text = "喂，需要你点一下"
		"done":
			_bubble_label.text = "干完啦 · " + _fmt_time(elapsed)
		"ended":
			_bubble_label.text = "收工了"
		_:
			_bubble_label.text = "打盹中…"
	_update_passthrough()


func _current_action() -> String:
	if _state == "needs_input":
		return "等你确认"
	if _state == "done":
		return "已结束"
	if _tail.detail != "":
		return _tail.detail
	if _tail.tool_name != "":
		return _tail.tool_name
	return "思考中"


func _state_title() -> String:
	match _state:
		"working":
			return "干活中"
		"needs_input":
			return "等你点一下"
		"done":
			return "干完了"
		"ended":
			return "收工了"
		_:
			return "待机中"


func _state_color() -> Color:
	match _state:
		"working":
			return C_WORK
		"needs_input":
			return C_WARN
		"done":
			return C_OK
		_:
			return C_DIM


func _elapsed() -> float:
	var start := _num(_entry, "started_at")
	if start <= 0.0:
		return 0.0
	var end := _num(_entry, "finished_at")
	if end <= 0.0:
		end = Time.get_unix_time_from_system()
	return maxf(0.0, end - start)


func _num(entry: Dictionary, key: String) -> float:
	var value = entry.get(key)
	if typeof(value) == TYPE_FLOAT or typeof(value) == TYPE_INT:
		return float(value)
	return 0.0


func _fmt_time(seconds: float) -> String:
	var total := int(maxf(0.0, seconds))
	return "%02d:%02d" % [int(total / 60.0), total % 60]


# ---------------------------------------------------------------- animation


func _animate() -> void:
	var bob := 0.0
	var rot := 0.0
	var stretch := 1.0
	match _state:
		"working":
			bob = sin(_t * 4.4) * 4.5
			rot = sin(_t * 2.3) * 0.02
		"needs_input":
			bob = -absf(sin(_t * 5.2)) * 9.0
			rot = sin(_t * 8.0) * 0.03
		"done":
			if _done_timer > 0.0:
				bob = -absf(sin(_t * 8.0)) * 14.0 * (_done_timer / 1.4)
		_:
			bob = sin(_t * 1.7) * 3.0
			stretch = 1.0 + sin(_t * 1.7) * 0.006

	_pet.position = _pet_base_pos + Vector2(0.0, bob)
	_pet.rotation = rot
	_pet.scale = Vector2(2.0 - stretch, stretch)

	if _state == "needs_input":
		_pet.modulate = Color(1.0, 0.93, 0.62 + 0.16 * sin(_t * 8.0))
	else:
		_pet.modulate = Color.WHITE


func _update_hover(delta: float) -> void:
	var mouse := _mouse_local()
	if _hit_test(mouse):
		_hover_hold = HOVER_GRACE
	else:
		_hover_hold = maxf(0.0, _hover_hold - delta)

	var want := _hover_hold > 0.0
	if want == _hover:
		return
	_hover = want
	_panel.visible = _hover
	_update_passthrough()
	queue_redraw()


func _mouse_local() -> Vector2:
	var pointer := DisplayServer.mouse_get_position()
	var origin := DisplayServer.window_get_position()
	return Vector2(pointer - origin)


func _hit_test(point: Vector2) -> bool:
	if _menu_open and _menu_rect.has_point(point):
		return true
	if _panel.visible and _panel_rect.has_point(point):
		return true
	if _bubble_rect.has_point(point):
		return true
	return _pet_hit(point)


func _pet_hit(point: Vector2) -> bool:
	if not _pet_rect.has_point(point) or _pet_image == null:
		return false
	var uv := (point - _pet_rect.position) / _pet_rect.size
	var px := clampi(int(uv.x * float(_pet_image.get_width())), 0, _pet_image.get_width() - 1)
	var py := clampi(int(uv.y * float(_pet_image.get_height())), 0, _pet_image.get_height() - 1)
	return _pet_image.get_pixel(px, py).a > 0.2


func _update_passthrough() -> void:
	var extra: Array = []
	if _bubble.visible:
		extra.append(_bubble_rect)
	if _panel.visible:
		extra.append(_panel_rect)
	if _menu_open:
		extra.append(_menu_rect)
	var key := "%s|%s|%s" % [_bubble.visible, _panel.visible, _menu_open]
	if key == _passthrough_key:
		return
	_passthrough_key = key

	var region: PackedVector2Array = Silhouette.build(_pet_image, _pet_rect, extra, WIN_SIZE)
	if region.is_empty():
		region = Silhouette.full_rect(WIN_SIZE)
	DisplayServer.window_set_mouse_passthrough(region, 0)


func _draw() -> void:
	# Speech-bubble tail (hidden while the hover panel is covering that spot).
	if _bubble.visible and not _panel.visible:
		var cx := _bubble_rect.position.x + _bubble_rect.size.x * 0.5
		var y := _bubble_rect.end.y - 3.0
		draw_colored_polygon(PackedVector2Array([
			Vector2(cx - 9.0, y),
			Vector2(cx + 9.0, y),
			Vector2(cx, y + 12.0),
		]), C_PANEL)


# ---------------------------------------------------------------- input


func _input(event: InputEvent) -> void:
	if not (event is InputEventMouseButton) or not event.pressed:
		return
	var mouse := _mouse_local()
	if event.button_index == MOUSE_BUTTON_LEFT:
		if _menu_open:
			if not _menu_rect.has_point(mouse):
				_set_menu_open(false)
			return
		if _pet_hit(mouse):
			DisplayServer.window_start_drag()
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		if _pet_hit(mouse) or (_menu_open and _menu_rect.has_point(mouse)):
			_set_menu_open(not _menu_open, mouse)


func _set_menu_open(open: bool, at: Vector2 = Vector2.ZERO) -> void:
	_menu_open = open
	_menu.visible = open
	if open:
		var pos := Vector2(
			clampf(at.x, 4.0, WIN_SIZE.x - _menu.size.x - 4.0),
			clampf(at.y, 4.0, WIN_SIZE.y - _menu.size.y - 4.0)
		)
		_menu.position = pos
		_menu_rect = Rect2(pos, _menu.size)
	_update_passthrough()


func _on_menu_action(action: String) -> void:
	match action:
		"quit":
			get_tree().quit()
		"cycle":
			_pinned_id = _store.next_session(str(_entry.get("session_id", "")))
			_refresh_status()
		"unpin":
			_pinned_id = ""
			_refresh_status()
	_set_menu_open(false)


# ---------------------------------------------------------------- config


func _load_config() -> void:
	if not FileAccess.file_exists(CONFIG_PATH):
		_center_on_screen()
		return
	var file := FileAccess.open(CONFIG_PATH, FileAccess.READ)
	if file == null:
		_center_on_screen()
		return
	var data = JSON.parse_string(file.get_as_text())
	if typeof(data) != TYPE_DICTIONARY:
		_center_on_screen()
		return
	var saved = data.get("position")
	if typeof(saved) == TYPE_ARRAY and saved.size() == 2:
		DisplayServer.window_set_position(Vector2i(int(saved[0]), int(saved[1])))
	else:
		_center_on_screen()
	_pinned_id = str(data.get("pinned", ""))


func _center_on_screen() -> void:
	var usable := DisplayServer.screen_get_usable_rect()
	var pos := Vector2i(
		usable.position.x + usable.size.x - int(WIN_SIZE.x) - 48,
		usable.position.y + usable.size.y - int(WIN_SIZE.y) - 64
	)
	DisplayServer.window_set_position(pos)


func _maybe_save_position(delta: float) -> void:
	_save_accum += delta
	if _save_accum < 2.0:
		return
	_save_accum = 0.0
	var pos := DisplayServer.window_get_position()
	if pos == _last_saved_pos:
		return
	_last_saved_pos = pos
	var file := FileAccess.open(CONFIG_PATH, FileAccess.WRITE)
	if file == null:
		return
	file.store_string(JSON.stringify({
		"position": [pos.x, pos.y],
		"pinned": _pinned_id,
	}))
