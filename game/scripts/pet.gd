extends Control
## Fishpet: a borderless, always-on-top, per-pixel-transparent overlay that
## shows what the local Claude Code sessions are doing.
##
## Data flow: hook.py writes one small JSON per session -> this script polls
## that directory twice a second and tails the transcript for the current tool.

const StatusStore = preload("res://scripts/status_store.gd")
const TranscriptTail = preload("res://scripts/transcript_tail.gd")
const Silhouette = preload("res://scripts/silhouette.gd")
const Reminders = preload("res://scripts/reminders.gd")
const SettingsPanel = preload("res://scripts/settings_panel.gd")

const STATE_DIR := "I:/PetFish/state"
const CONFIG_PATH := "I:/PetFish/window.json"
const FONT_PATH := "C:/Windows/Fonts/msyh.ttc"
const RIG_SILHOUETTE_PATH := "res://assets/pet_spine/pet_silhouette.png"
const RIG_JSON_PATH := "res://assets/pet_spine/pet.spine-json"
const RIG_ATLAS_PATH := "res://assets/pet_spine/pet.atlas"

# Wide enough for the character on the left and the cards on its right: the
# panels never sit on top of the pet, and while one is open she turns and
# presents it with the right arm.
const WIN_SIZE := Vector2(760, 480)
const PET_TARGET_H := 170.0
const PET_BOTTOM := 472.0
const PET_CENTER_X := 168.0
const POLL_INTERVAL := 0.5
const HOVER_GRACE := 0.25
const SLACK_AFTER := 600.0
const NOTICE_SECS := 8.0
# Bubble / card positions are derived from the pet's live on-screen box in
# _layout_ui(), so they track PET_TARGET_H instead of being hard-coded for one
# size (the 170 px pet sits lower than the old 340 px one, so fixed rects drift).
## Right-click menu size: five 30 px buttons plus padding.  Also used to clamp
## its top so the taller menu still fits inside WIN_SIZE.
const MENU_SIZE := Vector2(150, 186)

# Geometry of the rig's visible content, measured from a setup-pose capture:
# source alpha bbox and the node-local origin it maps from.  The rig is 1:1
# with the source art, so screen = rig.position + (source - origin) * scale.
const RIG_SRC_BBOX := Rect2i(197, 132, 599, 820)
const RIG_LOCAL_ORIGIN := Vector2(470.0, 132.0)

# The seated and prone poses are separate Spine skeletons (their bodies, arms and
# props differ structurally from the standing rig), so they are separate rigs
# that swap in for the "working" and "slack" states.  Unlike the standing rig,
# their bones are authored directly in canvas coordinates, so the node-local
# origin is the canvas origin (0,0): screen = rig.position + source * scale.
const SEATED_JSON_PATH := "res://assets/pet_spine/seated.spine-json"
const SEATED_ATLAS_PATH := "res://assets/pet_spine/seated.atlas"
const SEATED_SILHOUETTE_PATH := "res://assets/pet_spine/seated_silhouette.png"
const PRONE_JSON_PATH := "res://assets/pet_spine/prone.spine-json"
const PRONE_ATLAS_PATH := "res://assets/pet_spine/prone.atlas"
const PRONE_SILHOUETTE_PATH := "res://assets/pet_spine/prone_silhouette.png"

const SEATED_SRC_BBOX := Rect2i(67, 105, 1147, 1112)
const SEATED_CANVAS := Vector2(1280, 1280)
const PRONE_SRC_BBOX := Rect2i(0, 17, 1536, 980)
const PRONE_CANVAS := Vector2(1536, 1024)
const RIG_FADE_SPEED := 12.0

# drink chain: 100 / 250 / 500 ml -> 1 / 2 / 3 sips.  Clip lengths live in the
# Spine file (drink_in 1.2 s, drink_sip 1.0 s, drink_out 1.2 s) and the chain
# advances on the track entry finishing, so there is nothing to keep in sync
# here -- the old DRINK_IN/SIP/OUT constants drifted out of date and are gone.
const SIP_ML := 150.0

const C_PANEL := Color(0.06, 0.09, 0.17, 0.94)
const C_BORDER := Color(0.36, 0.62, 0.95, 0.55)
const C_TEXT := Color(0.88, 0.93, 1.0)
const C_DIM := Color(0.58, 0.67, 0.82)
const C_WORK := Color(0.45, 0.75, 1.0)
const C_WARN := Color(1.0, 0.78, 0.30)
const C_OK := Color(0.45, 0.90, 0.62)

var _font: Font
var _rig: SpineSprite
var _rig_seated: SpineSprite
var _rig_prone: SpineSprite
## The three pose rigs and the fade that swaps between pose families.  Each rig
## keeps its own silhouette for hit-testing and the Windows draw region.
var _rigs := {}
var _rig_loops := {}
var _sil_images := {}
var _sil_rects := {}
var _shown_rig := "standing"
var _target_rig := "standing"
var _fade_alpha := 1.0
var _fade_dir := 0  # -1 fade out, 0 settled, +1 fade in
var _pet_image: Image
var _pet_rect := Rect2()
## The silhouette is authored as the union of every pose, so it is larger than
## the setup-pose sprite: this is the rect it maps onto.
var _sil_rect := Rect2()
var _anim := ""

var _bubble: Panel
var _bubble_label: Label
var _bubble_rect := Rect2()

var _panel: Panel
var _state_label: Label
var _action_label: Label
var _stats_label: Label
var _project_label: Label
var _water_line: Label
var _panel_rect := Rect2()

var _menu: Panel
var _menu_rect := Rect2()
var _menu_pos := Vector2.ZERO
var _menu_open := false

var _reminders
var _settings
var _settings_rect := Rect2()
var _settings_open := false
var _chime: AudioStreamPlayer

var _notice_text := ""
var _notice_timer := 0.0
var _attention_clip := ""
# The active chain and the queue of things waiting for it are separate: a
# reminder that arrives mid-sip waits its turn instead of cutting the sip, and
# two identical reminders collapse into one.
var _chain: Array = []
var _chain_clip := ""
var _chain_tail := ""
var _queue: Array = []
var _active_key := ""
var _mix_native := false
# Stable roles: right-click menu = display 1; reminder settings = display 2.
# It also names the loop held while a card is up, so the notebook variant
# ("working") gets its own _in/_out clips for free -- see _present_pose().
var _present_clip := "present"
# "" (no card up) / "in" (raising the palm) / "hold" (looping the offer, or the
# writing loop while the user types into the card) / "out" (lowering)
var _present_phase := ""

var _store
var _tail

var _entry: Dictionary = {}
var _state := "idle"
var _state_age := 0.0
var _t := 0.0
var _poll_accum := 0.0
var _save_accum := 0.0
var _hover := false
var _hover_hold := 0.0
var _pinned_id := ""
var _last_saved_pos := Vector2i(99999, 99999)
var _passthrough_key := ""

## Test scenes set this before adding the pet to the tree.  The overlay then
## leaves the window alone: no borderless/topmost/transparent flags, no
## per-pixel click-through and no saved position, so a crashed test cannot
## leave an invisible window over the desktop (PERFORMANCE_DIAGNOSIS_20261024).
var test_window := false
## Cursor position used instead of the real one while `test_window` is set.
var _test_pointer := Vector2(-9999, -9999)


func _ready() -> void:
	_setup_window()
	_load_font()
	_load_pet()
	_build_ui()
	_store = StatusStore.new("user://preview_state" if test_window else STATE_DIR)
	_tail = TranscriptTail.new()
	_setup_reminders()
	_load_config()
	_refresh_status()
	_update_passthrough()


func _setup_window() -> void:
	if test_window:
		return
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
	var target_h := _target_height()

	_rig = _make_rig(RIG_JSON_PATH, RIG_ATLAS_PATH, RIG_SRC_BBOX, RIG_LOCAL_ORIGIN, target_h)
	if _rig == null:
		push_error("pet: could not load the standing Spine rig")
		return
	_rig_seated = _make_rig(SEATED_JSON_PATH, SEATED_ATLAS_PATH, SEATED_SRC_BBOX, Vector2.ZERO, target_h)
	_rig_prone = _make_rig(PRONE_JSON_PATH, PRONE_ATLAS_PATH, PRONE_SRC_BBOX, Vector2.ZERO, target_h)

	_rigs = {"standing": _rig}
	if _rig_seated != null:
		_rigs["seated"] = _rig_seated
	if _rig_prone != null:
		_rigs["prone"] = _rig_prone
	for rig in _rigs.values():
		rig.z_index = 0
		add_child(rig)

	# The standing content box drives the bubble/card layout; the wider
	# seated/prone poses may overhang it, but the panels draw above the rig.
	_pet_rect = _content_rect(RIG_SRC_BBOX, target_h)

	_sil_images = {
		"standing": _load_silhouette(RIG_SILHOUETTE_PATH),
		"seated": _load_silhouette(SEATED_SILHOUETTE_PATH),
		"prone": _load_silhouette(PRONE_SILHOUETTE_PATH),
	}
	if _sil_images["standing"] == null:
		_sil_images["standing"] = _placeholder_silhouette()
	# A missing seated/prone silhouette falls back to the standing union, which
	# is large enough to avoid clipping (it just hit-tests a little loosely).
	for rig_name in ["seated", "prone"]:
		if _sil_images[rig_name] == null:
			_sil_images[rig_name] = _sil_images["standing"]
	_sil_rects = {}
	for rig_name in _rigs:
		match rig_name:
			"seated":
				_sil_rects[rig_name] = _sil_rect_for(_rig_seated, Vector2.ZERO, SEATED_CANVAS)
			"prone":
				_sil_rects[rig_name] = _sil_rect_for(_rig_prone, Vector2.ZERO, PRONE_CANVAS)
			_:
				_sil_rects[rig_name] = _sil_rect_for(_rig, RIG_LOCAL_ORIGIN, Vector2(1024, 1024))
	_pet_image = _sil_images["standing"]
	_sil_rect = _sil_rects["standing"]

	_setup_mix()
	_play("idle")


## Target pet height: 170 px in the real overlay, overridable by tests.
func _target_height() -> float:
	var target_h := PET_TARGET_H
	if test_window and OS.has_environment("FISHPET_PET_H"):
		var asked := OS.get_environment("FISHPET_PET_H").to_float()
		if asked > 0.0:
			target_h = asked
	return target_h


## Build one SpineSprite, scaled to `target_h` and bottomed at the shared
## baseline.  `origin` is the source-space point that maps to the node's local
## origin: (470,132) for the standing rig, (0,0) for seated/prone.
func _make_rig(json_path: String, atlas_path: String, bbox: Rect2i, origin: Vector2, target_h: float) -> SpineSprite:
	var data = _make_skeleton_data(json_path, atlas_path)
	if data == null:
		return null
	var rig := SpineSprite.new()
	rig.skeleton_data_res = data
	var scale_f := target_h / float(bbox.size.y)
	rig.scale = Vector2(scale_f, scale_f)
	var draw_size := Vector2(bbox.size) * scale_f
	var draw_pos := Vector2(PET_CENTER_X - draw_size.x * 0.5, PET_BOTTOM - draw_size.y)
	rig.position = draw_pos - (Vector2(bbox.position) - origin) * scale_f
	rig.z_index = 0
	return rig


func _content_rect(bbox: Rect2i, target_h: float) -> Rect2:
	var scale_f := target_h / float(bbox.size.y)
	var draw_size := Vector2(bbox.size) * scale_f
	return Rect2(Vector2(PET_CENTER_X - draw_size.x * 0.5, PET_BOTTOM - draw_size.y), draw_size)


## The screen rect a rig's full-canvas silhouette maps onto.
func _sil_rect_for(rig: SpineSprite, origin: Vector2, canvas: Vector2) -> Rect2:
	var scale_f := rig.scale.x
	return Rect2(rig.position - origin * scale_f, canvas * scale_f)


func _load_silhouette(path: String) -> Image:
	if ResourceLoader.exists(path):
		var tex := load(path) as Texture2D
		if tex != null:
			return tex.get_image()
	return null


func _placeholder_silhouette() -> Image:
	var image := Image.create(1024, 1024, false, Image.FORMAT_RGBA8)
	image.fill(Color(0.30, 0.55, 0.95, 0.9))
	return image


## Point hit-testing and the Windows draw region at the rig that is currently
## on screen; the passthrough polygon is rebuilt because it clips drawing.
func _apply_silhouette(rig_name: String) -> void:
	if _sil_images.has(rig_name) and _sil_rects.has(rig_name):
		_pet_image = _sil_images[rig_name]
		_sil_rect = _sil_rects[rig_name]
	_update_passthrough()


## Real cross-fades: one default mix on the animation state, and a slower pair
## mix where the poses are far apart (sitting to work is a bigger change than
## two idle breaths).  The old code passed a mix time as set_animation's third
## argument, which is the track index -- every transition was a hard cut.
func _setup_mix() -> void:
	if _rig == null:
		return
	var st := _rig.get_animation_state()
	if st == null:
		return
	_mix_native = st.has_method("set_default_mix")
	if _mix_native:
		st.set_default_mix(0.20)
		if st.has_method("set_mix"):
			for pair in [["idle", "working", 0.28], ["working", "idle", 0.28],
					["working", "slack", 0.30], ["slack", "working", 0.30],
					["idle", "needs_input", 0.16], ["needs_input", "idle", 0.16]]:
				st.set_mix(pair[0], pair[1], pair[2])
	print("MIX native=", _mix_native)


func _make_skeleton_data(json_path: String, atlas_path: String):
	if not ResourceLoader.exists(json_path) or not ResourceLoader.exists(atlas_path):
		return null
	var sf: SpineSkeletonFileResource = load(json_path)
	var atlas: SpineAtlasResource = load(atlas_path)
	if sf == null or atlas == null:
		return null
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	return data if data.is_skeleton_data_loaded() else null


func _layout_ui() -> void:
	# Glue the bubble and right-hand cards to the pet's actual on-screen box, so
	# they stay beside/above her regardless of PET_TARGET_H.  `_pet_rect` is the
	# character's 1:1 content box (top = hairline, end.x = rightmost pixel).
	var head_top := _pet_rect.position.y
	var col_x := _pet_rect.end.x + 24.0
	# Bubble floats just above the head; its tail (drawn in _draw) points at it.
	_bubble_rect = Rect2(PET_CENTER_X - 150.0, head_top - 67.0, 300.0, 52.0)
	# Cards sit in a right-hand column clear of the pet (which turns to present),
	# and start below the bubble so its tail is never covered by a card corner.
	var card_top := maxf(head_top - 20.0, _bubble_rect.end.y + 6.0)
	# The info card is text only: five short lines, and the widest one ("喝水
	# 1500 / 1500 ml · 久坐 120 分钟") measures 218 px at 12 px.  256 px leaves
	# the 226 px the labels need plus padding, 40% narrower than the old 428.
	_panel_rect = Rect2(col_x, card_top, 256.0, 142.0)
	# The menu is taller than the info card, so clamp it to stay on screen.
	_menu_pos = Vector2(col_x, minf(card_top, WIN_SIZE.y - MENU_SIZE.y - 6.0))
	# The settings card holds real controls, so it keeps the full column width.
	_settings_rect = Rect2(col_x, 14.0, 428.0, 452.0)


func _build_ui() -> void:
	_layout_ui()
	# Plain Panel + absolutely placed Labels: Panel never re-lays out its
	# children, so sizes stay exactly what we ask for.
	_bubble = _make_panel(_bubble_rect)
	_bubble_label = _place_label(_bubble, Vector2(13.0, 7.0), _bubble_rect.size - Vector2(26.0, 14.0), 15, C_TEXT)
	_bubble_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	_bubble_label.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	# Reminder lines can run long; let them wrap to a second line.
	_bubble_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_bubble_label.text_overrun_behavior = TextServer.OVERRUN_NO_TRIMMING
	_bubble_label.max_lines_visible = 2
	_bubble_label.text = "打盹中…"
	add_child(_bubble)

	_panel = _make_panel(_panel_rect)
	_panel.visible = false
	var inner_w := _panel_rect.size.x - 30.0
	_state_label = _place_label(_panel, Vector2(15.0, 8.0), Vector2(inner_w, 24.0), 16, C_WORK)
	_action_label = _place_label(_panel, Vector2(15.0, 34.0), Vector2(inner_w, 22.0), 14, C_TEXT)
	_stats_label = _place_label(_panel, Vector2(15.0, 58.0), Vector2(inner_w, 20.0), 13, C_DIM)
	_project_label = _place_label(_panel, Vector2(15.0, 80.0), Vector2(inner_w, 20.0), 12, C_DIM)
	_water_line = _place_label(_panel, Vector2(15.0, 101.0), Vector2(inner_w, 20.0), 12, C_DIM)
	add_child(_panel)

	_menu = _make_panel(Rect2(Vector2.ZERO, MENU_SIZE))
	_menu.visible = false
	var menu_box := VBoxContainer.new()
	menu_box.position = Vector2(12.0, 9.0)
	menu_box.size = Vector2(MENU_SIZE.x - 24.0, MENU_SIZE.y - 18.0)
	menu_box.add_theme_constant_override("separation", 4)
	_menu.add_child(menu_box)
	for item in [
		["喝水打卡", "water"],
		["提醒设置", "settings"],
		["切换会话", "cycle"],
		["取消固定", "unpin"],
		["退出", "quit"],
	]:
		var button := Button.new()
		button.text = item[0]
		button.focus_mode = Control.FOCUS_NONE
		button.custom_minimum_size = Vector2(MENU_SIZE.x - 24.0, 30)
		if _font != null:
			button.add_theme_font_override("font", _font)
			button.add_theme_font_size_override("font_size", 14)
		button.pressed.connect(_on_menu_action.bind(item[1]))
		menu_box.add_child(button)
	add_child(_menu)


# ---------------------------------------------------------------- reminders


func _setup_reminders() -> void:
	_reminders = Reminders.new()
	_reminders.name = "Reminders"
	if test_window:
		_reminders.data_path = "user://preview_reminders_%d.json" % OS.get_process_id()
	add_child(_reminders)
	if test_window:
		_reminders.set_process(false)
	_reminders.notice.connect(_on_notice)
	_reminders.water_logged.connect(_on_water_logged)

	_settings = SettingsPanel.new()
	_settings.name = "Settings"
	_settings.position = _settings_rect.position
	_settings.size = _settings_rect.size
	_settings.visible = false
	add_child(_settings)
	_settings.setup(_font, _reminders)
	_settings.closed.connect(_close_settings)

	_chime = AudioStreamPlayer.new()
	_chime.stream = _build_chime()
	_chime.volume_db = -7.0
	add_child(_chime)


## A soft two-tone ping, synthesised so the project needs no audio asset.
func _build_chime() -> AudioStreamWAV:
	var rate := 22050
	var count := int(rate * 0.85)
	var bytes := PackedByteArray()
	bytes.resize(count * 2)
	for i in count:
		var t := float(i) / rate
		var freq := 880.0 if t < 0.16 else 1174.7
		var env := exp(-4.5 * t) * minf(1.0, t / 0.008)
		var sample := sin(TAU * freq * t) * env + sin(TAU * freq * 2.0 * t) * env * 0.12
		var value := int(clampf(sample * 0.55, -1.0, 1.0) * 32767.0)
		bytes[i * 2] = value & 0xff
		bytes[i * 2 + 1] = (value >> 8) & 0xff
	var stream := AudioStreamWAV.new()
	stream.format = AudioStreamWAV.FORMAT_16_BITS
	stream.mix_rate = rate
	stream.stereo = false
	stream.data = bytes
	return stream


func _on_notice(kind: String, text: String) -> void:
	_show_notice(text)
	_attention_clip = str({"water": "water_remind", "sit": "hop_sit",
		"alarm": "hop_alarm", "memo": "hop_memo"}.get(kind, "hop_memo"))
	# A drink finishes safely; cards temporarily take priority over the loop.
	if not _chain_busy() and not _presenting():
		_enter_state()
	_play_chime()


func _on_water_logged(ml: int, total: int, goal: int) -> void:
	_attention_clip = ""
	var left := maxi(0, goal - total)
	var text := "陪你喝了 %d ml · 今天 %d ml" % [ml, total]
	if left <= 0:
		text = "喝够啦！今天 %d ml" % total
	elif left <= 300:
		text = "陪你喝了 %d ml，还差 %d ml" % [ml, left]
	_show_notice(text)
	# A bigger amount means more sips: 100 / 250 / 500 ml -> 1 / 2 / 3.
	# The opaque ceramic cup keeps a stable two-handed grip throughout.
	var sips := clampi(int(round(float(ml) / SIP_ML)), 1, 3)
	var drains := ["drink_sip", "drink_sip2", "drink_sip3"]
	var clips := ["drink_in"]
	for i in sips:
		clips.append(drains[i])
	clips.append("drink_out")
	start_chain(clips)


func _show_notice(text: String) -> void:
	_notice_text = text
	_notice_timer = NOTICE_SECS
	_refresh_texts()


func _dismiss_notice() -> void:
	_attention_clip = ""
	_notice_timer = 0.0
	_notice_text = ""
	_refresh_texts()
	if not _chain_busy() and not _presenting():
		_enter_state()


func _play_chime() -> void:
	if test_window:
		return
	if _chime != null and _reminders != null and _reminders.sound_on():
		_chime.play()


func _open_settings() -> void:
	_settings_open = true
	_settings.visible = true
	_settings.reload()
	_set_menu_open(false)
	_hover = false
	_show_panel(false)
	_begin_present()
	_update_passthrough()


func _close_settings() -> void:
	_settings_open = false
	_settings.visible = false
	_update_passthrough()


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
	if _notice_timer > 0.0 and _attention_clip == "":
		_notice_timer -= delta
		if _notice_timer <= 0.0:
			_notice_timer = 0.0
			_notice_text = ""
			_refresh_texts()
	_poll_accum += delta
	if _poll_accum >= POLL_INTERVAL:
		_poll_accum = 0.0
		_refresh_status()
	_update_hover(delta)
	_animate(delta)
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
	# A session that has been quiet for a long while is "slacking off" now.
	if state == "idle" and Time.get_unix_time_from_system() - _num(entry, "ts") > SLACK_AFTER:
		state = "slack"
	_set_state(state)
	_refresh_texts()


func _set_state(next_state: String) -> void:
	if next_state == _state:
		return
	_state = next_state
	_state_age = 0.0
	if not _chain_busy():
		if _presenting():
			_request_rig("standing")
			_play(_present_clip)
		elif _attention_clip != "":
			_enter_state()
		elif _state == "done":
			_request_rig("standing")
			_play("done", false)
		else:
			_enter_state()
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
	if _reminders != null:
		_water_line.text = "喝水 %d / %d ml   ·   久坐 %d 分钟" % [
			_reminders.today_ml(), _reminders.goal_ml(), _reminders.sit_minutes()]

	if _notice_timer > 0.0:
		_bubble_label.text = _notice_text
	else:
		match _state:
			"working":
				_bubble_label.text = action if action != "" else "思考中…"
			"needs_input":
				_bubble_label.text = "喂，需要你点一下"
			"done":
				_bubble_label.text = "干完啦 · " + _fmt_time(elapsed)
			"ended":
				_bubble_label.text = "收工了"
			"slack":
				_bubble_label.text = "摸鱼中… 有事叫我"
			_:
				_bubble_label.text = "打盹中…"
	_update_passthrough()


func _current_action() -> String:
	if _state == "needs_input":
		return "等你确认"
	if _state == "done":
		return "已结束"
	if _state == "slack":
		return "摸鱼中"
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
		"slack":
			return "摸鱼中"
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


func _anim_for(state: String) -> String:
	match state:
		"working":
			return "working"
		"needs_input":
			return "needs_input"
		"done":
			return "done"
		"slack":
			return "slack"
		_:
			return "idle"


## Which rig shows a given session state.  The seated rig replaces the standing
## "working" pose, and the prone rig replaces "slack"; a missing rig falls back
## to the standing pose rather than dropping the state.
func _pose_rig(state: String) -> String:
	if state == "working" and _rig_seated != null:
		return "seated"
	if state == "slack" and _rig_prone != null:
		return "prone"
	return "standing"


## The loop clip a state plays on its own rig (seated/prone only differ here).
func _state_loop(state: String) -> String:
	if state == "working":
		return "seat_work_loop"
	if state == "slack":
		return "prone_read_loop"
	return _anim_for(state)


## Loops that own a prop get an explicit entry and exit clip, so a prop is
## never attached or dropped between two frames.
const PROP_IN := {"working": "working_in", "slack": "slack_in"}
# An entry clip owns the prop too: if the state changes while it is running,
# it has to be left through the matching exit clip, not cut to idle.
const PROP_OUT := {
	"working": "working_out", "slack": "slack_out",
	"working_in": "working_out", "slack_in": "slack_out",
}


func _prop_in(anim: String) -> String:
	return PROP_IN.get(anim, "")


func _prop_out(anim: String) -> String:
	return PROP_OUT.get(anim, "")


## Ask for a chain of one-shot clips.  `key` merges duplicates: a second
## reminder of the same kind while one is already running or waiting is
## dropped, so a spamming hook cannot queue twenty hops.
func start_chain(clips: Array, key: String = "") -> void:
	if _rig == null:
		return
	if key != "" and (_active_key == key or _queue_has(key)):
		return
	if _chain_busy():
		# no lead yet: what she is holding when this finally starts is not known
		# until then, so the exit clip is added in _chain_next()
		_queue.append({"clips": clips.duplicate(), "key": key})
		return
	if _present_phase == "hold" or _present_phase == "in":
		# A card owns the stage: lower the offered hand first, then run the chain.
		# Otherwise a drink resets the pose underneath a still-raised hand, then
		# re-lowers it after the sip (the old double-present hiccup).
		_queue.append({"clips": clips.duplicate(), "key": key})
		_present_phase = "out"
		_play(_present_clip + "_out", false)
		return
	_begin_chain(_with_lead(clips), key)


## Put the prop of the loop she is in away first, in its own clip, so a
## reminder or a drink never pops the notebook out of her hands.
func _with_lead(clips: Array) -> Array:
	var full := clips.duplicate()
	var lead := _prop_out(_anim)
	if lead != "":
		full.push_front(lead)
	return full


func _queue_has(key: String) -> bool:
	for item in _queue:
		if str(item.get("key", "")) == key:
			return true
	return false


## Start the next queued chain, if one is waiting.  Returns true when it did.
func _drain_queue() -> bool:
	if _queue.is_empty():
		return false
	var item: Dictionary = _queue.pop_front()
	_begin_chain(_with_lead(item["clips"]), str(item.get("key", "")))
	return true


func _begin_chain(clips: Array, key: String = "") -> void:
	# Chains (drinks, hops) are standing clips; drop the seated/prone pose first.
	_request_rig("standing")
	_chain = clips.duplicate()
	_chain_clip = ""
	_chain_tail = ""
	_active_key = key
	# a reminder/drink takes the stage; a lowered offer is simply dropped
	if _present_phase == "out":
		_present_phase = ""
	_chain_next()


func _chain_busy() -> bool:
	return _chain_clip != "" or not _chain.is_empty()


func _chain_next() -> void:
	if _rig == null:
		_chain.clear()
		_queue.clear()
		return
	if _chain.is_empty():
		_chain_clip = ""
		_active_key = ""
		if _drain_queue():
			return
		var tail := _chain_tail
		_chain_tail = ""
		if tail != "":
			if tail.begins_with("present"):
				_present_phase = "hold"
			_play(tail)
			return
		if _presenting():
			# a card is waiting for the stage: raise the offer properly rather
			# than cutting to the pose with whatever was in her hands
			_begin_present()
			return
		_enter_state()
		return
	var first := _chain_clip == ""
	_chain_clip = str(_chain.pop_front())
	# Only the first clip starts from the setup pose: clips key just the bones
	# they move, so without the reset an interrupted stretch leaves an arm up.
	# Later steps must continue from the previous pose instead of snapping.
	_play(_chain_clip, false, first)


## Play the clip the current state wants, entering (and leaving) prop loops
## through their own clips so nothing pops on or off.
func _enter_state() -> void:
	if _rig == null:
		return
	# The seated/prone rigs own the working/slack loops; everything else (and any
	# reminder/hop) is a standing pose.
	var rig_name := "standing"
	if _attention_clip == "":
		rig_name = _pose_rig(_state)
	if rig_name != "standing":
		_request_rig(rig_name)
		_play_on(rig_name, _state_loop(_state))
		return
	_request_rig("standing")
	var loop := _attention_clip if _attention_clip != "" else _anim_for(_state)
	# "done" is a one-shot: _animate takes her back to idle once it has played,
	# so it must not be requested as a loop (a looping clip never completes and
	# she would cheer forever when the state lands mid-chain)
	var once := loop == "done"
	if _anim == loop:
		return
	var enter := _prop_in(loop)
	# already on the way into this loop: just finish the entry
	if enter != "" and _anim == enter:
		_play(loop)
		return
	var clips: Array = []
	var out := _prop_out(_anim)
	if out != "":
		clips.append(out)
	if enter != "":
		clips.append(enter)
	if clips.is_empty():
		_play(loop, not once)
		return
	_chain = clips
	_chain_clip = ""
	# no tail: the state may have changed again by the time this drains, so the
	# loop clip is re-derived when the chain ends rather than captured here
	_chain_tail = ""
	_chain_next()


func _tick_chain() -> void:
	if _rig == null or _chain_clip == "":
		return
	if _clip_done():
		_chain_next()


## True once the one-shot clip on track 0 has played to its end.
func _clip_done() -> bool:
	if _rig == null:
		return true
	var entry := _rig.get_animation_state().get_current(0)
	return entry == null or entry.is_complete()


## reset_to_setup wipes leftovers from the previous clip; only the first step of
## a chain needs it (later steps continue from the previous pose).
func _play(anim: String, loop: bool = true, reset_to_setup: bool = false) -> void:
	if _rig == null:
		return
	var st := _rig.get_animation_state()
	# Re-requesting the clip that is already running is a no-op, but a chain can
	# legitimately ask for the same clip twice in a row (two sips): that must
	# restart the track, otherwise the second sip is skipped and a 250 ml drink
	# plays as a single sip.
	if not reset_to_setup and anim == _anim:
		var cur := st.get_current(0)
		if cur != null and not cur.is_complete():
			return
	_anim = anim
	if reset_to_setup:
		var sk := _rig.get_skeleton()
		if sk != null:
			sk.set_to_setup_pose()
	# set_animation's third argument is the TRACK INDEX, not a mix time.  The
	# cross-fade comes from the state's default mix, which _load_pet installs
	# (plus a few pair mixes); a setup-pose reset is the one hard cut.
	var entry := st.set_animation(anim, loop, 0)
	if entry != null:
		if reset_to_setup:
			entry.set_mix_duration(0.0)
		elif not _mix_native:
			# the build has no set_default_mix(); fall back to a per-entry fade
			entry.set_mix_duration(0.18)


## Play a clip on a specific rig (the seated/prone loops live on their own
## SpineSprite, outside the standing `_rig` state machine).
func _play_on(rig_name: String, anim: String, loop: bool = true) -> void:
	var rig: SpineSprite = _rigs.get(rig_name)
	if rig == null:
		return
	if _rig_loops.get(rig_name, "") == anim:
		return
	_rig_loops[rig_name] = anim
	rig.get_animation_state().set_animation(anim, loop, 0)


## Ask for a pose family.  The swap fades the current rig out, switches the
## silhouette, then fades the new rig in, so the Windows draw region always
## matches the pose that is on screen (independent pose switch; a real stand ->
## sit transition needs separate art).
func _request_rig(rig_name: String) -> void:
	if rig_name == _target_rig:
		return
	_target_rig = rig_name
	if rig_name == _shown_rig:
		_fade_dir = 1
	else:
		_fade_dir = -1


func _apply_rig_modulate() -> void:
	var pulse := _state == "needs_input" and _notice_timer <= 0.0
	for rig_name in _rigs:
		var rig: SpineSprite = _rigs[rig_name]
		if rig == null:
			continue
		if rig_name == _shown_rig:
			rig.visible = true
			if pulse and rig_name == "standing":
				rig.modulate = Color(1.0, 0.97, 0.86 + 0.10 * sin(_t * 8.0), _fade_alpha)
			else:
				rig.modulate = Color(1.0, 1.0, 1.0, _fade_alpha)
		else:
			rig.visible = false


## Hover still shows session information but does not steal a reminder's pose.
func _presenting() -> bool:
	return _menu_open or _settings_open


## The pose that should be held while a card is up.  Writing into one of the
## settings fields turns the offer into "hold the notebook and jot it down",
## which is the ordinary working loop -- the same clip names are also its
## pick-up (`working_in`) and put-away (`working_out`) clips.
func _present_pose() -> String:
	if _note_taking():
		return "working"
	return "present2" if _settings_open else "present"


## True while the user is writing into the settings card.
func _note_taking() -> bool:
	return _settings_open and _settings != null and _settings.is_typing()


## Derive the pose from the actual UI, never from how many times it opened.
func _begin_present() -> void:
	_present_clip = _present_pose()
	# Presenting a card is a standing pose; bring the standing rig back first.
	_request_rig("standing")
	if _chain_busy():
		# a reminder owns the stage; the offer starts when it is done
		return
	if _present_phase == "hold":
		if _present_clip == _anim:
			return
		# The pose swaps under raised palms -- unless one side carries a prop.
		# The notebook has its own pick-up / put-away clips, so cutting straight
		# to the writing loop would pop the pad into her hands.
		var put_away := _prop_out(_anim)
		var pick_up := _prop_in(_present_clip)
		if put_away == "" and pick_up == "":
			# card -> card: the palms are already up, only the pose swaps
			_play(_present_clip)
			return
		var swap: Array = []
		if put_away != "":
			swap.append(put_away)
		if pick_up != "":
			swap.append(pick_up)
		_begin_chain(swap)
		_chain_tail = _present_clip
		return
	# a new offer: put any held prop away, raise the hand, then hold the pose
	_present_phase = "in"
	var clips: Array = []
	var lead := _prop_out(_anim)
	if lead != "":
		clips.append(lead)
	clips.append(_present_clip + "_in")
	_begin_chain(clips)
	_chain_tail = _present_clip


func _show_panel(show_it: bool) -> void:
	if _panel.visible == show_it:
		return
	_panel.visible = show_it
	_update_passthrough()


func _animate(delta: float) -> void:
	if _rig == null:
		return
	var showing := _presenting()
	if _chain_busy():
		_tick_chain()
	elif _present_phase == "out":
		# Lowering the offered hand.  This runs even while a card is still up
		# (a drink was requested from the settings card, which stays open), so
		# the queued chain must start as soon as the hand is down instead of
		# the present pose re-raising it mid-lower.
		if _clip_done():
			_present_phase = ""
			if _drain_queue():
				return
			_enter_state()
	elif showing:
		if _present_phase == "hold" and _present_clip != _present_pose():
			# the pose has to change under a card that stays up: the user started
			# (or stopped) writing into one of the settings fields
			_begin_present()
		elif _anim == _present_clip + "_in":
			if _clip_done():
				_present_phase = "hold"
				_play(_present_clip)
		elif _anim == _present_clip:
			_present_phase = "hold"
		elif _present_phase != "in":
			# cards are up but the pose is not: a chain just ended, or the
			# panel opened while another clip was still finishing
			_begin_present()
	elif _present_phase != "" or _anim.begins_with("present"):
		# The cards closed: leave the offer.  If the pose she was holding is the
		# very loop her session state wants (she was writing in the notebook that
		# "working" wants anyway), keep it rather than stowing the pad and taking
		# it straight back out.
		var wanted := _attention_clip if _attention_clip != "" else _anim_for(_state)
		if _anim == _present_clip and _present_clip == wanted:
			_present_phase = ""
			_enter_state()
			return
		# Otherwise lower the offered hand before anything else.
		_present_phase = "out"
		_play(_present_clip + "_out", false)
	elif _state == "done" and _anim == "done" and _clip_done():
		# "done" leaves when its animation has played through, not on a timer;
		# the state stays "done" so the bubble keeps reporting the session
		_play("idle")
	# Cross-rig fade: fade the shown rig out, swap the silhouette, fade the new
	# rig in.  The needs_input warm pulse rides on the standing rig's modulate.
	if _fade_dir != 0:
		_fade_alpha = clampf(_fade_alpha + _fade_dir * delta * RIG_FADE_SPEED, 0.0, 1.0)
		if _fade_dir < 0 and _fade_alpha <= 0.0:
			_fade_alpha = 0.0
			_shown_rig = _target_rig
			_apply_silhouette(_shown_rig)
			_fade_dir = 1
		elif _fade_dir > 0 and _fade_alpha >= 1.0:
			_fade_alpha = 1.0
			_fade_dir = 0
	_apply_rig_modulate()


func _update_hover(delta: float) -> void:
	# The cards own the right side while they are up: no hover card on top.
	if _settings_open or _menu_open:
		_hover_hold = 0.0
		if _hover:
			_hover = false
			_show_panel(false)
		return
	var mouse := _mouse_local()
	if _hit_test(mouse):
		_hover_hold = HOVER_GRACE
	else:
		_hover_hold = maxf(0.0, _hover_hold - delta)

	var want := _hover_hold > 0.0
	if want == _hover:
		return
	_hover = want
	_show_panel(_hover)
	queue_redraw()


func _mouse_local() -> Vector2:
	if test_window:
		# the real cursor must not open hover cards during a scripted run
		return _test_pointer
	var pointer := DisplayServer.mouse_get_position()
	var origin := DisplayServer.window_get_position()
	return Vector2(pointer - origin)


func _hit_test(point: Vector2) -> bool:
	if _settings_open and _settings_rect.has_point(point):
		return true
	if _menu_open and _menu_rect.has_point(point):
		return true
	if _panel.visible and _panel_rect.has_point(point):
		return true
	if _bubble_rect.has_point(point):
		return true
	return _pet_hit(point)


func _pet_hit(point: Vector2) -> bool:
	if not _sil_rect.has_point(point) or _pet_image == null:
		return false
	var uv := (point - _sil_rect.position) / _sil_rect.size
	var px := clampi(int(uv.x * float(_pet_image.get_width())), 0, _pet_image.get_width() - 1)
	var py := clampi(int(uv.y * float(_pet_image.get_height())), 0, _pet_image.get_height() - 1)
	return _pet_image.get_pixel(px, py).a > 0.2


func _update_passthrough() -> void:
	# a test owns its window: making it click-through would let the run swallow
	# clicks on whatever is behind it if it ever failed to reach quit()
	if test_window:
		return
	var extra: Array = []
	if _bubble.visible:
		extra.append(_bubble_rect)
	if _panel.visible:
		extra.append(_panel_rect)
	if _menu_open:
		extra.append(_menu_rect)
	if _settings_open:
		extra.append(_settings_rect)
	var key := "%s|%s|%s|%s|%s" % [_bubble.visible, _panel.visible, _menu_open, _settings_open, _shown_rig]
	if key == _passthrough_key:
		return
	_passthrough_key = key

	var region: PackedVector2Array = Silhouette.build(_pet_image, _sil_rect, extra, WIN_SIZE)
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
	# Use the event's own position: DisplayServer's cursor position is in screen
	# space and lags behind by a frame when the window has just moved.
	var mouse: Vector2 = event.position
	if _settings_open:
		if event.button_index == MOUSE_BUTTON_LEFT and not _settings_rect.has_point(mouse):
			_close_settings()
		return
	if event.button_index == MOUSE_BUTTON_LEFT:
		if _menu_open:
			if not _menu_rect.has_point(mouse):
				_set_menu_open(false)
			return
		if _notice_timer > 0.0 and _bubble_rect.has_point(mouse):
			_dismiss_notice()
			return
		if _pet_hit(mouse):
			DisplayServer.window_start_drag()
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		if _pet_hit(mouse) or (_menu_open and _menu_rect.has_point(mouse)):
			_set_menu_open(not _menu_open)


func _set_menu_open(open: bool) -> void:
	_menu_open = open
	_menu.visible = open
	if open:
		# Fixed at the character's right, level with her chest, so it never
		# covers the body she is turning to present.
		_menu.position = _menu_pos
		_menu_rect = Rect2(_menu_pos, _menu.size)
		_begin_present()
	_update_passthrough()


func _on_menu_action(action: String) -> void:
	match action:
		"quit":
			get_tree().quit()
		"water":
			_reminders.log_water(250)
		"settings":
			_open_settings()
			return
		"cycle":
			_pinned_id = _store.next_session(str(_entry.get("session_id", "")))
			_refresh_status()
		"unpin":
			_pinned_id = ""
			_refresh_status()
	_set_menu_open(false)


# ---------------------------------------------------------------- config


func _load_config() -> void:
	# the test window belongs to the harness, and its position must not be
	# written into the user's window.json
	if test_window:
		return
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
	if test_window:
		return
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
