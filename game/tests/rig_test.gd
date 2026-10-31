extends Node2D
## Dev-only harness: loads the pet Spine rig, plays every animation and writes
## PNG frames so the deformation can be inspected without launching the pet.
##
## Run:  Godot --path game res://tests/rig_test.tscn --resolution 700x900

const Stage = preload("res://tests/test_stage.gd")
const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT_DIR := "I:/PetFish/tools/_debug/frames"

# The drink sample is three clips that the app chains for a 250 ml mug:
# drink_in -> drink_sip x 2 -> drink_out. They are marked not to loop.
const SEQUENCE := [
	["idle", 4.0, true],
	["working", 2.2, true],
	["needs_input", 3.0, true],
	["done", 1.4, true],
	["drink_in", 0.9, false],
	["drink_sip", 1.0, false],
	["drink_sip", 1.0, false],
	["drink_out", 0.9, false],
	["stretch", 2.8, true],
	["slack", 6.0, true],
	["cheer", 1.6, true],
]

var _sprite: SpineSprite
var _label: Label
var _idx := 0
var _t := 0.0
var _next_shot := 0.0
var _shot_idx := 0


func _ready() -> void:
	Stage.begin(self, 120.0, "FishPet rig_test")
	DirAccess.make_dir_recursive_absolute(OUT_DIR)

	var bg := ColorRect.new()
	bg.color = Color(0.09, 0.10, 0.13)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)

	var grid := GridBg.new()
	grid.mouse_filter = Control.MOUSE_FILTER_IGNORE
	grid.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(grid)

	_label = Label.new()
	_label.position = Vector2(16, 12)
	_label.add_theme_font_size_override("font_size", 22)
	add_child(_label)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	print("sf=", sf, " atlas=", atlas)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	print("loaded=", data.is_skeleton_data_loaded(), " ver=", data.get_version())
	if not data.is_skeleton_data_loaded():
		return

	var names := []
	for a in data.get_animations():
		names.append(a.get_name())
	print("animations=", names)

	_sprite = SpineSprite.new()
	_sprite.skeleton_data_res = data
	add_child(_sprite)

	# Rendered-local box of the rig: RIG_LOCAL_ORIGIN is (470,132) in the source
	# art and RIG_SRC_BBOX is (197,132,599,820), so the figure is 599 wide and
	# its centre sits 26.5 px right of the origin.
	const TOP_LOCAL := 0.0
	const FEET_LOCAL := 820.0
	const WIDTH_LOCAL := 599.0
	const CENTER_X_LOCAL := 26.5

	var win := get_viewport_rect().size
	var scale_f := minf(win.x * 0.90 / WIDTH_LOCAL, (win.y - 90.0) / (FEET_LOCAL - TOP_LOCAL))
	_sprite.scale = Vector2(scale_f, scale_f)
	_sprite.position = Vector2(
		win.x * 0.5 - CENTER_X_LOCAL * scale_f,
		40.0 - TOP_LOCAL * scale_f)
	print("window=", win, " scale=", scale_f)

	_play(0)


func _play(i: int) -> void:
	_idx = i
	_t = 0.0
	_next_shot = 0.0
	var anim: String = SEQUENCE[i][0]
	var loop: bool = SEQUENCE[i][2]
	_label.text = "%s  (%.1fs, %s)" % [anim, SEQUENCE[i][1], "loop" if loop else "once"]
	_sprite.get_animation_state().set_animation(anim, loop, 0.0)


func _process(delta: float) -> void:
	if _sprite == null:
		return
	_t += delta
	if _t >= _next_shot:
		_next_shot += 0.28
		_capture()
	if _t >= float(SEQUENCE[_idx][1]):
		if _idx + 1 >= SEQUENCE.size():
			Stage.ok("rig_test finished")
		else:
			_play(_idx + 1)


func _capture() -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var anim: String = SEQUENCE[_idx][0]
	var path := "%s/%s_%02d.png" % [OUT_DIR, anim, _shot_idx]
	img.save_png(path)
	_shot_idx += 1


class GridBg extends Control:
	func _draw() -> void:
		var s := Vector2(40, 40)
		var x := 0.0
		while x < size.x:
			draw_line(Vector2(x, 0), Vector2(x, size.y), Color(1, 1, 1, 0.045), 1.0)
			x += s.x
		var y := 0.0
		while y < size.y:
			draw_line(Vector2(0, y), Vector2(size.x, y), Color(1, 1, 1, 0.045), 1.0)
			y += s.y
