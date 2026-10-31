extends Node
## Dev-only: rotate one bone at a time from the setup pose and report the box of
## pixels that move. A weight that reaches the wrong layer shows up here as a
## changed box in the wrong part of the figure.
##
## Run: Godot --path game res://tests/bone_test.tscn

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/bones"

const BONES := [
	"root", "hip", "spine", "chest", "neck", "head",
	"hairL1", "hairL2", "hairL3", "hairR1", "hairR2", "hairR3",
	"tail1", "tail2", "tailFin", "skirt",
	"armL1", "armL2", "handL", "armR1", "armR2", "handR", "cup",
]

var _vp: SubViewport
var _sprite: SpineSprite
var _neutral: Image


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	_vp = SubViewport.new()
	_vp.size = Vector2i(720, 860)
	_vp.transparent_bg = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	_sprite = SpineSprite.new()
	_sprite.skeleton_data_res = data
	_sprite.position = Vector2(360, 20)
	_vp.add_child(_sprite)
	_sprite.set_process(false)  # keep manual bone edits from being reset

	var sk := _sprite.get_skeleton()
	sk.set_to_setup_pose()
	sk.update_world_transform(SpineConstant.Physics_None)
	_neutral = await _shot()
	_neutral.save_png(OUT + "/_neutral.png")
	print("neutral saved")

	for bone_name in BONES:
		var bone = sk.find_bone(bone_name)
		if bone == null:
			print("MISSING ", bone_name)
			continue
		sk.set_to_setup_pose()
		bone.set_rotation(18.0)
		sk.update_world_transform(SpineConstant.Physics_None)
		var img: Image = await _shot()
		img.save_png("%s/%s.png" % [OUT, bone_name])
		print("saved ", bone_name)
	print("done")
	get_tree().quit()


func _shot() -> Image:
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	return _vp.get_texture().get_image()


func _bbox(img: Image) -> Rect2i:
	return Rect2i(img.get_region(Rect2i(0, 0, img.get_width(), img.get_height())).get_used_rect())


func _diff(img: Image) -> Array:
	var a := _neutral.get_data()
	var b := img.get_data()
	var w := img.get_width()
	var h := img.get_height()
	var x0 := w
	var y0 := h
	var x1 := -1
	var y1 := -1
	var n := 0
	for y in range(h):
		var row := y * w * 4
		for x in range(w):
			var i := row + x * 4
			var d := 0
			for k in range(4):
				d = maxi(d, absi(int(a[i + k]) - int(b[i + k])))
			if d > 16:
				n += 1
				x0 = mini(x0, x)
				y0 = mini(y0, y)
				x1 = maxi(x1, x)
				y1 = maxi(y1, y)
	if n == 0:
		return [Rect2i(), 0]
	return [Rect2i(x0, y0, x1 - x0 + 1, y1 - y0 + 1), n]
