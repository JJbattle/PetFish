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
const ChatPanel = preload("res://scripts/chat_panel.gd")
const Deepseek = preload("res://scripts/deepseek.gd")
const GitFeed = preload("res://scripts/git_feed.gd")
const Updater = preload("res://scripts/updater.gd")
const ActivitySession = preload("res://scripts/activity_session.gd")

const STATE_DIR := "res://../state"
const CONFIG_PATH := "user://window.json"
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
# Slack "偷着乐" beat: while she reads prone, the face flips to the happy eye and
# mouth attachments for a short stretch, then back to neutral, on a randomized
# cooldown.  The read loop keeps running underneath so the body never stops; only
# the prone rig's two face slots change (docs/ART_BRIEF_HAPPY_EXPRESSION.md).
const HAPPY_BEAT_MIN := 2.0
const HAPPY_BEAT_MAX := 3.0
const HAPPY_COOLDOWN_MIN := 24.0
const HAPPY_COOLDOWN_MAX := 42.0
# Slack alternates between the reading pose and the "doodle the whale" sketch
# pose every SLACK_SWITCH_MIN..MAX seconds, so 摸鱼 has a little variety.  The
# sketch rig's face is baked in, so the happy-beat only runs while reading.
const SLACK_SWITCH_MIN := 25.0
const SLACK_SWITCH_MAX := 55.0
const NOTICE_SECS := 8.0
# Bubble / card positions are derived from the pet's live on-screen box in
# _layout_ui(), so they track PET_TARGET_H instead of being hard-coded for one
# size (the 170 px pet sits lower than the old 340 px one, so fixed rects drift).
## Right-click menu size: six 30 px buttons plus padding.  Also used to clamp
## its top so the taller menu still fits inside WIN_SIZE.
const MENU_SIZE := Vector2(150, 218)

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
const PRONE_SKETCH_JSON_PATH := "res://assets/pet_spine/prone_sketch.spine-json"
const PRONE_SKETCH_ATLAS_PATH := "res://assets/pet_spine/prone_sketch.atlas"
const PRONE_SKETCH_SILHOUETTE_PATH := "res://assets/pet_spine/prone_sketch_silhouette.png"
# The follow-along rig is authored in y-up world coords (spine-godot flips y), so
# its node-local content sits in a 1024x1024 box just like seated/prone, and the
# same origin-ZERO placement applies.
const ACTIVITY_JSON_PATH := "res://assets/activity_spine/activity_standing.spine-json"
const ACTIVITY_ATLAS_PATH := "res://assets/activity_spine/activity_standing.atlas"
const ACTIVITY_SILHOUETTE_PATH := "res://assets/activity_spine/activity_standing_silhouette.png"
const ACTIVITY_SRC_BBOX := Rect2i(225, 65, 589, 848)
const ACTIVITY_CANVAS := Vector2(1024, 1024)

const SEATED_SRC_BBOX := Rect2i(275, 108, 780, 798)
const SEATED_CANVAS := Vector2(1280, 1280)
const PRONE_SRC_BBOX := Rect2i(25, 78, 1448, 914)
const PRONE_CANVAS := Vector2(1536, 1024)
const PRONE_SKETCH_SRC_BBOX := Rect2i(29, 32, 1506, 979)
const PRONE_SKETCH_CANVAS := Vector2(1600, 1040)
# Head-height rescale (docs/POSE_HEAD_SCALE.md): the standing source head is
# 355 px tall, seated 379 px, prone 528 px.  Scale seated/prone by 355/head so
# every pose's head lands at the same ~74 px on screen; the props (book, pillow,
# whale cushion) scale with the whole rig once.
const SEATED_HEAD_RATIO := 355.0 / 379.0
const PRONE_HEAD_RATIO := 355.0 / 528.0
const PRONE_SKETCH_HEAD_RATIO := 355.0 / 557.0
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
var _rig_prone_sketch: SpineSprite
var _rig_activity: SpineSprite
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
var _chat_panel
var _deepseek
var _feed
var _updater
var _chat_rect := Rect2()
var _chat_open := false
## True when the panel was opened by a plain notice (not a reminder) and should
## close itself again once `_notice_timer` runs out.
var _chat_auto_close := false
## The collapsed bubble is the chat entry in every state.  `_bubble_speech` is the
## last assistant reply, `_bubble_notice` the pending reminder line; the bubble
## shows whichever is current, else live working progress, else the idle prompt.
var _bubble_speech := ""
var _bubble_notice := ""
## Weekly feed sync: `_feed_pending` means new content is waiting for the user to
## click the bubble (their consent); `_feed_text` is what to reveal on that click.
var _feed_pending := false
var _feed_text := ""
var _chime: AudioStreamPlayer

var _notice_timer := 0.0
var _attention_clip := ""
## The kind of the pending reminder ("water"/"sit"/"alarm"/"memo"/"").  Water and
## sit act from the bubble (their prompt + action live in a small card above it);
## alarm and memo keep the chat card's top banner.
var _notice_kind := ""
## The small action card shown for a water/sit reminder, so the user can log water
## or start the follow-along without opening the chat card at all.
var _notice_card: Panel
var _notice_card_box: VBoxContainer
var _notice_card_rect := Rect2()
## Follow-along session: `_activity` owns timing/config, `_activity_active` means
## the activity rig owns the stage (blocking the normal state/chain/present logic).
var _activity
var _activity_active := false
var _activity_bar_accum := 0.0
var _activity_bar_title: Label
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
# Happy-beat state for the prone (slack) rig: `_happy` is whether the face is on
# the happy attachments right now, and `_happy_timer` counts down to the next
# flip (beat length while happy, cooldown while neutral).
var _happy := false
var _happy_timer := 0.0
# Slack pose alternation: `_slack_sketching` flips between the reading and
# sketch rigs; `_slack_switch_timer` counts down to the next flip.
var _slack_sketching := false
var _slack_switch_timer := 0.0
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
	_store = StatusStore.new("user://preview_state" if test_window else ProjectSettings.globalize_path(STATE_DIR))
	_tail = TranscriptTail.new()
	_setup_reminders()
	_setup_feed()
	_setup_updater()
	_load_config()
	_happy_timer = randf_range(HAPPY_COOLDOWN_MIN, HAPPY_COOLDOWN_MAX)
	_slack_switch_timer = randf_range(SLACK_SWITCH_MIN, SLACK_SWITCH_MAX)
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
	# The three poses are authored at different source sizes, so feeding each the
	# same `target_h` would draw their heads at different screen sizes.  Rescale
	# seated/prone by the head-height ratios above; `_make_rig` then divides by
	# the pose's own bbox height, so this nets out to the desired whole-rig scale.
	var standing_scale := target_h / float(RIG_SRC_BBOX.size.y)
	var seated_h := float(SEATED_SRC_BBOX.size.y) * standing_scale * SEATED_HEAD_RATIO
	var prone_h := float(PRONE_SRC_BBOX.size.y) * standing_scale * PRONE_HEAD_RATIO
	var prone_sketch_h := float(PRONE_SKETCH_SRC_BBOX.size.y) * standing_scale * PRONE_SKETCH_HEAD_RATIO

	_rig = _make_rig(RIG_JSON_PATH, RIG_ATLAS_PATH, RIG_SRC_BBOX, RIG_LOCAL_ORIGIN, target_h)
	if _rig == null:
		push_error("pet: could not load the standing Spine rig")
		return
	_rig_seated = _make_rig(SEATED_JSON_PATH, SEATED_ATLAS_PATH, SEATED_SRC_BBOX, Vector2.ZERO, seated_h)
	_rig_prone = _make_rig(PRONE_JSON_PATH, PRONE_ATLAS_PATH, PRONE_SRC_BBOX, Vector2.ZERO, prone_h)
	_rig_prone_sketch = _make_rig(PRONE_SKETCH_JSON_PATH, PRONE_SKETCH_ATLAS_PATH, PRONE_SKETCH_SRC_BBOX, Vector2.ZERO, prone_sketch_h)
	_rig_activity = _make_rig(ACTIVITY_JSON_PATH, ACTIVITY_ATLAS_PATH, ACTIVITY_SRC_BBOX, Vector2.ZERO, target_h)

	_rigs = {"standing": _rig}
	if _rig_seated != null:
		_rigs["seated"] = _rig_seated
	if _rig_prone != null:
		_rigs["prone"] = _rig_prone
	if _rig_prone_sketch != null:
		_rigs["prone_sketch"] = _rig_prone_sketch
	if _rig_activity != null:
		_rigs["activity"] = _rig_activity
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
		"prone_sketch": _load_silhouette(PRONE_SKETCH_SILHOUETTE_PATH),
		"activity": _load_silhouette(ACTIVITY_SILHOUETTE_PATH),
	}
	if _sil_images["standing"] == null:
		_sil_images["standing"] = _placeholder_silhouette()
	# A missing seated/prone silhouette falls back to the standing union, which
	# is large enough to avoid clipping (it just hit-tests a little loosely).
	for rig_name in ["seated", "prone", "prone_sketch", "activity"]:
		if _sil_images[rig_name] == null:
			_sil_images[rig_name] = _sil_images["standing"]
	_sil_rects = {}
	for rig_name in _rigs:
		match rig_name:
			"seated":
				_sil_rects[rig_name] = _sil_rect_for(_rig_seated, Vector2.ZERO, SEATED_CANVAS)
			"prone":
				_sil_rects[rig_name] = _sil_rect_for(_rig_prone, Vector2.ZERO, PRONE_CANVAS)
			"prone_sketch":
				_sil_rects[rig_name] = _sil_rect_for(_rig_prone_sketch, Vector2.ZERO, PRONE_SKETCH_CANVAS)
			"activity":
				_sil_rects[rig_name] = _sil_rect_for(_rig_activity, Vector2.ZERO, ACTIVITY_CANVAS)
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
	# The collapsed chat bubble floats just above the head and stops short of the
	# right-hand cards (the info card + menu still show on hover and must not
	# cover it), so it is narrower than the old 300 px progress bubble.
	_bubble_rect = Rect2(8.0, head_top - 67.0, minf(300.0, col_x - 16.0), 52.0)
	# The reminder action card floats above the bubble; water (3 amounts + 稍后)
	# and sit (跟练/已活动/稍后) both fit in this fixed height.
	_notice_card_rect = Rect2(8.0, maxf(6.0, _bubble_rect.position.y - 206.0),
		minf(270.0, col_x - 16.0), 200.0)
	# The menu and settings cards sit in a right-hand column clear of the pet
	# (which turns to present); the menu starts below the bubble's tail.
	var card_top := maxf(head_top - 20.0, _bubble_rect.end.y + 6.0)
	# The info card lives in the right-hand column, stacked just above the menu,
	# so the head-top stays clear for the chat bubble / chat card alone.  While it
	# is up, the one-line bubble hides (see _refresh_texts) so they never overlap.
	_panel_rect = Rect2(col_x, card_top - 142.0 - 8.0, 256.0, 142.0)
	# The menu is taller than the info card, so clamp it to stay on screen.
	_menu_pos = Vector2(col_x, minf(card_top, WIN_SIZE.y - MENU_SIZE.y - 6.0))
	# The settings card holds real controls, so it keeps the full column width.
	_settings_rect = Rect2(col_x, 14.0, 428.0, 452.0)
	# The chat card (input + history + reminders) floats above the head in the
	# bubble's old spot; the right-hand column keeps only the settings card.
	_chat_rect = Rect2(PET_CENTER_X - 160.0, maxf(6.0, head_top - 300.0), 320.0, 290.0)


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
	_bubble_label.text = "💬 和大肥鱼聊聊…"
	# The bubble is the collapsed chat entry: always up unless the chat card is
	# open, showing a pending reminder, live working progress, or the last reply.
	_bubble.visible = false
	add_child(_bubble)

	# The reminder action card (water amounts / sit follow-along) is a sibling of
	# the bubble, rebuilt each time a water/sit reminder fires.
	_notice_card = _make_panel(_notice_card_rect)
	_notice_card.visible = false
	_notice_card_box = VBoxContainer.new()
	_notice_card_box.position = Vector2(12.0, 9.0)
	_notice_card_box.size = _notice_card_rect.size - Vector2(24.0, 18.0)
	_notice_card_box.add_theme_constant_override("separation", 4)
	_notice_card.add_child(_notice_card_box)
	add_child(_notice_card)

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
		["检查更新", "update"],
		["同步投喂", "feed"],
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

	_chat_panel = ChatPanel.new()
	_chat_panel.name = "Chat"
	_chat_panel.position = _chat_rect.position
	_chat_panel.size = _chat_rect.size
	_chat_panel.visible = false
	_chat_panel.setup(_font)
	_chat_panel.closed.connect(_on_chat_closed)
	_chat_panel.send.connect(_on_chat_send)
	_chat_panel.dismissed.connect(_on_reminder_dismissed)
	_chat_panel.collapse.connect(_close_chat)
	add_child(_chat_panel)

	_deepseek = Deepseek.new()
	_deepseek.name = "Deepseek"
	if test_window:
		_deepseek.secrets_path = "user://preview_secrets_%d.json" % OS.get_process_id()
	_deepseek.chat_reply.connect(_on_chat_reply)
	add_child(_deepseek)


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
	_settings.setup(_font, _reminders, _deepseek)
	_settings.closed.connect(_close_settings)

	_chime = AudioStreamPlayer.new()
	_chime.stream = _build_chime()
	_chime.volume_db = -7.0
	add_child(_chime)


func _setup_feed() -> void:
	_feed = GitFeed.new()
	_feed.name = "GitFeed"
	if test_window:
		_feed.data_path = "user://preview_feed_%d.json" % OS.get_process_id()
	add_child(_feed)
	if test_window:
		_feed.set_process(false)
	_feed.feed_ready.connect(_on_feed_ready)
	_feed.feed_checked.connect(_on_feed_checked)


## New weekly content arrived: prompt in the bubble only (no card, no pose
## change).  The user consents by clicking the bubble, which reveals the content.
func _on_feed_ready(text: String) -> void:
	_feed_text = text
	_feed_pending = true
	_refresh_texts()


## A manual "检查更新" finished with nothing new (or a transient failure).  It is
## an informational line in the chat card, never the reminder banner, so it never
## clobbers a pending alarm/memo.
func _on_feed_checked(message: String) -> void:
	if not _chat_open:
		_open_chat(false)
	_chat_panel.notice(message)
	_notice_timer = NOTICE_SECS
	_chat_auto_close = true


func _setup_updater() -> void:
	_updater = Updater.new()
	_updater.name = "Updater"
	add_child(_updater)
	_updater.update_ready.connect(_on_update_ready)
	_updater.update_checked.connect(_on_update_checked)


## A newer build's installer finished downloading: surface its path in the chat
## card so the user knows where to run it.
func _on_update_ready(path: String, version: String) -> void:
	if not _chat_open:
		_open_chat(false)
	_chat_panel.notice("发现新版本 v%s，安装包已下载到：\n%s" % [version, path])
	_notice_timer = NOTICE_SECS
	_chat_auto_close = true


## A manual "检查更新" finished with nothing new / no installer yet / a failure.
func _on_update_checked(message: String) -> void:
	if not _chat_open:
		_open_chat(false)
	_chat_panel.notice(message)
	_notice_timer = NOTICE_SECS
	_chat_auto_close = true


## Clicking the bubble while a feed is pending is consent: open the chat card and
## show the full item as a distinct yellow bold line (the two-line bubble can't
## hold it).
func _reveal_feed() -> void:
	var text := _feed_text
	_feed_pending = false
	_feed_text = ""
	_open_chat(false)
	_chat_panel.feed_message(text)


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
	_attention_clip = str({"water": "water_remind", "sit": "hop_sit",
		"alarm": "hop_alarm", "memo": "hop_memo"}.get(kind, "hop_memo"))
	_show_notice(text, kind)
	# A drink finishes safely; cards temporarily take priority over the loop.
	if not _chain_busy() and not _presenting():
		_enter_state()
	_play_chime()


func _on_water_logged(ml: int, total: int, goal: int) -> void:
	_attention_clip = ""
	_bubble_notice = ""
	_notice_kind = ""
	# Logging water resolves the pending drink reminder, so drop its banner (and
	# the bubble action card) too.
	_chat_panel.clear_reminder()
	_hide_notice_card()
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


func _show_notice(text: String, kind: String = "") -> void:
	_notice_kind = kind
	if kind == "water" or kind == "sit":
		# Water and sit act from the bubble: show the line plus an action card
		# above it, and never open the chat card / banner for them.
		_close_chat()
		_bubble_notice = text
		_refresh_texts()
		_show_notice_card(kind, text)
		_update_passthrough()
		return
	if not _chat_open:
		_open_chat(false)
	if _attention_clip != "":
		# A real reminder (alarm/memo) needs an action, so it opens the banner at
		# the top of the card (never the chat log) and also survives as a bubble
		# line while the card is collapsed.
		_bubble_notice = text
		_chat_panel.reminder(text)
	else:
		# A plain drink-logged notice is informational: append it to the log and
		# let the panel close itself after NOTICE_SECS.
		_chat_panel.notice(text)
	_notice_timer = NOTICE_SECS
	# A plain notice (drink logged etc.) closes the panel on its own after
	# NOTICE_SECS; a reminder keeps its attention clip set, so the panel stays
	# until the user acts on or dismisses it.
	_chat_auto_close = (_attention_clip == "")


func _dismiss_notice() -> void:
	_attention_clip = ""
	_bubble_notice = ""
	_notice_kind = ""
	_chat_panel.clear_reminder()
	_hide_notice_card()
	_notice_timer = 0.0
	_chat_auto_close = false
	_refresh_texts()
	if not _chain_busy() and not _presenting():
		_enter_state()


## The reminder banner's "确认": acknowledge the reminder but keep the chat card
## open so the user can carry on talking.
func _on_reminder_dismissed() -> void:
	_dismiss_notice()


## (Re)build the small action card above the bubble for a water/sit reminder.
func _show_notice_card(kind: String, text: String) -> void:
	if _notice_card == null:
		return
	_clear_notice_card()
	var title := _make_label(13, C_WARN)
	title.text = text
	_notice_card_box.add_child(title)
	if kind == "water":
		for item in [["🥤 150 ml", "log_150"], ["🥤 250 ml", "log_250"],
				["🥤 500 ml", "log_500"], ["稍后", "later"]]:
			_notice_card_box.add_child(_action_button(item[0], item[1]))
	else:
		for item in [["跟我动 1 分钟", "activity"], ["我已经活动了", "stood"],
				["稍后", "later"]]:
			_notice_card_box.add_child(_action_button(item[0], item[1]))
	_notice_card.position = _notice_card_rect.position
	_notice_card.visible = true


## The follow-along's first tap: choose one of the three routines in place.
func _show_activity_pick() -> void:
	if _notice_card == null:
		return
	_clear_notice_card()
	var title := _make_label(13, C_WORK)
	title.text = "选一套，跟着动 1 分钟"
	_notice_card_box.add_child(title)
	for item in [["原地巡逻", "activity_a"], ["海草舒展", "activity_b"],
			["肩膀放松", "activity_c"], ["返回", "activity_back"]]:
		_notice_card_box.add_child(_action_button(item[0], item[1]))
	_notice_card.visible = true


func _clear_notice_card() -> void:
	# Detach now (so a rebuild in the same frame never shows stale buttons), then
	# free deferred: the caller is usually inside one of these buttons' pressed
	# signals, and freeing the emitting node mid-signal is not safe.
	for child in _notice_card_box.get_children():
		_notice_card_box.remove_child(child)
		child.queue_free()


func _hide_notice_card() -> void:
	if _notice_card != null:
		_notice_card.visible = false


func _action_button(text: String, action: String) -> Button:
	var button := Button.new()
	button.text = text
	button.focus_mode = Control.FOCUS_NONE
	button.custom_minimum_size = Vector2(0, 30)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	if _font != null:
		button.add_theme_font_override("font", _font)
		button.add_theme_font_size_override("font_size", 14)
	button.pressed.connect(_on_notice_action.bind(action))
	return button


func _on_notice_action(action: String) -> void:
	match action:
		"log_150":
			_reminders.log_water(150)
		"log_250":
			_reminders.log_water(250)
		"log_500":
			_reminders.log_water(500)
		"stood":
			# "I already moved": confirm the activity, then settle back.
			_reminders.stand_up()
			_dismiss_notice()
		"activity":
			_show_activity_pick()
		"activity_a", "activity_b", "activity_c":
			_start_activity(action)
		"activity_back":
			_show_notice_card("sit", _bubble_notice)
		"activity_pause":
			if _activity != null:
				_activity.pause()
			_refresh_activity_bar()
		"activity_resume":
			if _activity != null:
				_activity.resume()
			_refresh_activity_bar()
		"activity_end":
			_end_activity(false)
		"activity_done":
			_end_activity(true)
		"activity_skip":
			_end_activity(false)
		"later":
			_hide_notice_card()


# ---------------------------------------------------------------- activity


func _start_activity(action: String) -> void:
	var pkg := action.trim_prefix("activity_")
	if _activity == null:
		_activity = ActivitySession.new()
	if not _activity.start(pkg):
		# Missing clips (B/C not built yet): keep the sit card and say so.
		_show_notice_card("sit", "这套动作还在准备中，先试试原地巡逻吧")
		return
	_hide_notice_card()
	_attention_clip = ""
	_activity_active = true
	# The follow-along runs on the standing rig (the real character), so the
	# clips below are standing clips, not the old redrawn activity rig.
	_request_rig("standing")
	# start() already advanced to segment 0; play it now.
	_play(_activity.current_clip(), _activity.current_loop())
	_refresh_activity_bar()
	_refresh_texts()
	_update_passthrough()


func _tick_activity(delta: float) -> void:
	if _activity == null:
		return
	var before: String = _activity.current_clip()
	_activity.advance(minf(delta, 0.5))
	if _activity.state() == "awaiting_confirmation":
		_on_activity_finished()
		return
	var after: String = _activity.current_clip()
	if after != before and after != "":
		_play(after, _activity.current_loop())
		_refresh_activity_bar()
	_activity_bar_accum += delta
	if _activity_bar_accum >= 1.0:
		_activity_bar_accum = 0.0
		if _activity_bar_title != null and _activity.state() == "running":
			_activity_bar_title.text = _activity_status_text()


func _on_activity_finished() -> void:
	_activity_active = false
	_request_rig("standing")
	# The activity drove the standing rig's clips; hand it back to the normal
	# state pose now that the session owns the stage again.
	_enter_state()
	_show_activity_done()


func _show_activity_done() -> void:
	if _notice_card == null:
		return
	_clear_notice_card()
	var title := _make_label(13, C_WARN)
	title.text = "这一分钟做完了吗？"
	_notice_card_box.add_child(title)
	_notice_card_box.add_child(_action_button("完成活动", "activity_done"))
	_notice_card_box.add_child(_action_button("暂不记录", "activity_skip"))
	_notice_card.visible = true


func _end_activity(completed: bool) -> void:
	_activity_active = false
	if _activity != null:
		_activity.stop()
	_request_rig("standing")
	_hide_notice_card()
	if completed:
		_reminders.stand_up()
		_dismiss_notice()
	else:
		# Ended early / "暂不记录": re-offer the sit reminder and resume its bounce.
		_attention_clip = "hop_sit"
		_show_notice_card("sit", _bubble_notice)
		_refresh_texts()
		if not _chain_busy() and not _presenting():
			_enter_state()
	_update_passthrough()


func _refresh_activity_bar() -> void:
	if _notice_card == null or _activity == null:
		return
	_clear_notice_card()
	_activity_bar_title = _make_label(13, C_WORK)
	_activity_bar_title.text = _activity_status_text()
	_notice_card_box.add_child(_activity_bar_title)
	if _activity.state() == "paused":
		_notice_card_box.add_child(_action_button("继续", "activity_resume"))
	else:
		_notice_card_box.add_child(_action_button("暂停", "activity_pause"))
	_notice_card_box.add_child(_action_button("结束", "activity_end"))
	_notice_card.visible = true


func _activity_status_text() -> String:
	if _activity == null:
		return ""
	var seg: String = _activity.current_clip()
	var seg_name: String = {
		"needs_input": "站稳准备", "march": "原地踏步",
		"heel": "缓慢提踵", "idle": "放松",
		"side_bend_l": "左侧弯", "side_bend_r": "右侧弯",
		"shrug": "耸肩", "chest_open": "低位开胸",
	}.get(seg, "")
	var remain: int = int(ceilf(_activity.total_remaining()))
	if _activity.state() == "paused":
		return "%s · 已暂停 · 剩 %ds" % [_activity.package_name(), remain]
	return "%s · %s · 剩 %ds" % [_activity.package_name(), seg_name, remain]


func _play_chime() -> void:
	if test_window:
		return
	if _chime != null and _reminders != null and _reminders.sound_on():
		_chime.play()


func _open_settings() -> void:
	_close_chat()
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


## The chat card is a plain overlay above the head, not one of the "present a
## card" poses, so opening it leaves the pet on whatever state pose she is
## already holding; replies and reminders live in the panel itself.
func _open_chat(focus: bool = true) -> void:
	_close_settings()
	_set_menu_open(false)
	_chat_open = true
	_chat_auto_close = false
	_chat_panel.visible = true
	if focus:
		_chat_panel.focus_input()
	_hover = false
	_show_panel(false)
	_bubble.visible = false
	_update_passthrough()


func _close_chat() -> void:
	if not _chat_open:
		return
	_chat_open = false
	_chat_panel.visible = false
	_chat_auto_close = false
	_refresh_texts()
	_update_passthrough()


## The chat card's ✕: closing the panel acknowledges the reminder it was
## showing.  Clicking outside (in _input) only collapses to the bubble, so the
## reminder survives until this is pressed or the user acts on it.
func _on_chat_closed() -> void:
	if _attention_clip != "":
		_dismiss_notice()
	_close_chat()


func _on_chat_send(messages: Array) -> void:
	_deepseek.send(messages)


func _on_chat_reply(text: String, error: String) -> void:
	if error != "":
		_chat_panel.error(error)
	else:
		_bubble_speech = text
		_chat_panel.reply(text)
		_refresh_texts()


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
			_refresh_texts()
			if _chat_auto_close:
				_close_chat()
	_poll_accum += delta
	if _poll_accum >= POLL_INTERVAL:
		_poll_accum = 0.0
		_refresh_status()
	_update_hover(delta)
	_animate(delta)
	_tick_happy(delta)
	_tick_slack_pose(delta)
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
	if _activity_active:
		# The follow-along session owns the stage: record the state change but
		# don't swap clips away from the activity rig until the session ends.
		queue_redraw()
		return
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

	if _chat_open:
		# An active chat (or a reminder on top of it) owns the head-top spot.
		_bubble.visible = false
		_chat_panel.visible = true
	else:
		# Collapsed: the bubble is the chat entry in every state.  It shows a
		# pending notice/reminder, then live working progress, then the last
		# reply, then the idle prompt.  Hovering the pet keeps it up (the
		# right-hand cards no longer hide it).
		_bubble_label.text = _bubble_text()
		_bubble.visible = true
		_chat_panel.visible = false
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


## What the collapsed bubble shows: a pending notice/reminder first, then live
## working progress, then the last assistant reply, then the idle prompt.
func _bubble_text() -> String:
	if _activity_active:
		return _activity_status_text()
	if _bubble_notice != "":
		return _bubble_notice
	if _feed_pending:
		return "🔄 有新同步内容，点我查看"
	if _state == "working":
		return _working_bubble_text()
	if _bubble_speech != "":
		return _bubble_speech
	return "💬 和大肥鱼聊聊…"


## Two-line "progress" bubble for the working state: the tool she is on now,
## then the step count.  Detail is capped so a long Bash description can't push
## the step line out of the bubble; tool output is never surfaced.
func _working_bubble_text() -> String:
	var tool := str(_tail.tool_name)
	if tool == "":
		return "干活中…"
	var head := tool
	var detail := str(_tail.detail)
	if detail != "":
		if detail.length() > 20:
			detail = detail.substr(0, 19) + "…"
		head += " · " + detail
	var step := int(_tail.tool_count)
	if step > 0:
		return "%s\n第 %d 步" % [head, step]
	return head


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
	if state == "slack":
		if _slack_sketching and _rig_prone_sketch != null:
			return "prone_sketch"
		if _rig_prone != null:
			return "prone"
	return "standing"


## The loop clip a state plays on its own rig (seated/prone only differ here).
func _state_loop(state: String) -> String:
	if state == "working":
		return "seat_work_loop"
	if state == "slack":
		return "prone_sketch_loop" if _slack_sketching else "prone_read_loop"
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
	if _activity_active:
		# The activity session drives the rig; never enter a state pose under it.
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
	# The hover card replaces the one-line bubble while it is up; _refresh_texts
	# re-derives the bubble (and the passthrough region) for the new state.
	_refresh_texts()


func _animate(delta: float) -> void:
	if _rig == null:
		return
	if _activity_active:
		# The follow-along session owns the stage; block the normal state machine.
		_tick_activity(delta)
	else:
		_animate_state(delta)
	_tick_fade(delta)
	_apply_rig_modulate()


func _animate_state(delta: float) -> void:
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
## Cross-rig fade: fade the shown rig out, swap the silhouette, fade the new
## rig in.  The needs_input warm pulse rides on the standing rig's modulate.
func _tick_fade(delta: float) -> void:
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


## Flip the slack face to the "偷着乐" happy attachments for a short beat, then
## back to neutral.  Only the prone rig has the swappable eye/mouth slots; the
## sketch pose's face is baked into the body, so the beat pauses while she
## doodles.  Leaving slack always snaps the face back so a lingering happy beat
## never shows on the seated or standing pose.
func _tick_happy(delta: float) -> void:
	if _state != "slack" or _rig_prone == null or _slack_sketching:
		if _happy:
			_set_happy(false)
			_happy_timer = randf_range(HAPPY_COOLDOWN_MIN, HAPPY_COOLDOWN_MAX)
		return
	_happy_timer -= delta
	if _happy:
		if _happy_timer <= 0.0:
			_set_happy(false)
			_happy_timer = randf_range(HAPPY_COOLDOWN_MIN, HAPPY_COOLDOWN_MAX)
	else:
		if _happy_timer <= 0.0:
			_set_happy(true)
			_happy_timer = randf_range(HAPPY_BEAT_MIN, HAPPY_BEAT_MAX)


## Alternate the slack pose between reading and "doodle the whale" on a random
## schedule, so 摸鱼 stays varied.  The choice only changes while she is actually
## prone and unoccupied; a drink chain or an open card has her on the standing
## rig, and `_enter_state` re-derives the pose from `_slack_sketching` when she
## returns, so nothing fights for the stage.
func _tick_slack_pose(delta: float) -> void:
	if _state != "slack" or _rig_prone == null:
		# Leaving slack returns to reading, so a dangling doodle never persists.
		if _slack_sketching:
			_slack_sketching = false
			_slack_switch_timer = randf_range(SLACK_SWITCH_MIN, SLACK_SWITCH_MAX)
		return
	if _rig_prone_sketch == null or _chain_busy() or _presenting():
		return
	_slack_switch_timer -= delta
	if _slack_switch_timer <= 0.0:
		_slack_sketching = not _slack_sketching
		_slack_switch_timer = randf_range(SLACK_SWITCH_MIN, SLACK_SWITCH_MAX)
		_enter_state()


func _set_happy(on: bool) -> void:
	if _happy == on:
		return
	_happy = on
	if _rig_prone == null:
		return
	var skeleton := _rig_prone.get_skeleton()
	if skeleton == null:
		return
	var face := "happy" if on else "neutral"
	skeleton.set_attachment("prone_eyes", face)
	skeleton.set_attachment("prone_mouth", face)


func _update_hover(delta: float) -> void:
	# The settings or chat card owns the stage while it is up: hover neither
	# shows the info card nor re-opens the menu on top of it.
	if _settings_open or _chat_open:
		_hover_hold = 0.0
		if _hover:
			_hover = false
			_show_panel(false)
		return
	# The follow-along session owns the stage too: hovering must not open the info
	# card or the right-click menu, because presenting a card would turn her away
	# from the exercise pose.  The activity bar (pause/end) stays the only UI.
	if _activity_active:
		_hover_hold = 0.0
		if _hover:
			_hover = false
			_show_panel(false)
		if _menu_open:
			_set_menu_open(false)
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
	if _hover:
		# Hovering reveals the info card above her head and, without any
		# right-click, opens the small action menu on her right.
		_show_panel(true)
		if not _menu_open:
			_set_menu_open(true)
	else:
		_show_panel(false)
		if _menu_open:
			_set_menu_open(false)
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
	if _chat_panel.visible:
		extra.append(_chat_rect)
	if _notice_card != null and _notice_card.visible:
		extra.append(_notice_card_rect)
	var key := "%s|%s|%s|%s|%s|%s|%s" % [_bubble.visible, _panel.visible, _menu_open,
		_settings_open, _chat_panel.visible, _shown_rig, _notice_card != null and _notice_card.visible]
	if key == _passthrough_key:
		return
	_passthrough_key = key

	var region: PackedVector2Array = Silhouette.build(_pet_image, _sil_rect, extra, WIN_SIZE)
	if region.is_empty():
		region = Silhouette.full_rect(WIN_SIZE)
	DisplayServer.window_set_mouse_passthrough(region, 0)


func _draw() -> void:
	# Speech-bubble tail, pointing at the head.  The collapsed bubble no longer
	# sits under the hover cards, so it stays up whenever the bubble is visible.
	if _bubble.visible:
		var cx := clampf(PET_CENTER_X, _bubble_rect.position.x + 12.0, _bubble_rect.end.x - 12.0)
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
	if _notice_card != null and _notice_card.visible:
		# The reminder action card owns left-clicks while it is up: a click outside
		# it (and off the bubble) hides it, keeping the reminder pending.  Buttons
		# inside the card are handled by the buttons themselves.
		if event.button_index == MOUSE_BUTTON_LEFT:
			if not _notice_card_rect.has_point(mouse) \
					and not (_bubble.visible and _bubble_rect.has_point(mouse)):
				_hide_notice_card()
			return
	if _chat_open:
		if event.button_index == MOUSE_BUTTON_LEFT and not _chat_rect.has_point(mouse):
			# A click away just collapses the panel back to the bubble; only the
			# ✕ (or acting on the reminder) acknowledges a pending reminder.
			_close_chat()
		return
	if _settings_open:
		if event.button_index == MOUSE_BUTTON_LEFT and not _settings_rect.has_point(mouse):
			_close_settings()
		return
	if event.button_index == MOUSE_BUTTON_LEFT:
		# The bubble above the head is the chat entry: click it to open the chat
		# card (input + history + reminders).  It also still shows live progress
		# while working, and a click there opens the chat too.  A pending water/sit
		# reminder turns the click into its action card instead of the chat.
		if _bubble.visible and _bubble_rect.has_point(mouse):
			if _activity_active:
				# During a follow-along the bubble shows its live status; a click
				# re-opens the pause/end bar instead of the chat.
				_refresh_activity_bar()
			elif _feed_pending:
				# A pending feed turns the click into consent to reveal it.
				_reveal_feed()
			elif _notice_kind == "water" or _notice_kind == "sit":
				_show_notice_card(_notice_kind, _bubble_notice)
			else:
				_open_chat()
			return
		if _menu_open:
			if _menu_rect.has_point(mouse):
				return
			_set_menu_open(false)
			# fall through: a left-click on the pet still starts a drag
		if _pet_hit(mouse):
			DisplayServer.window_start_drag()
	elif event.button_index == MOUSE_BUTTON_RIGHT:
		if _pet_hit(mouse) or (_menu_open and _menu_rect.has_point(mouse)):
			_set_menu_open(not _menu_open)


func _set_menu_open(open: bool) -> void:
	# During a follow-along the menu is a non-exercise operation: ignore it so the
	# right-click (and any lingering hover) can't steal the stage from the pose.
	if open and _activity_active:
		return
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
		"update":
			_updater.check_now()
		"feed":
			_feed.check_now()
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
