extends Node
## Dev-only: render the presented open hand on its own, so its shape and
## placement against the sleeve can be judged without the hair behind it.
## Also renders the pose with the head / hair_r hidden to see what covers it.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/hand_solo"

var _vp: SubViewport
var _sprite: SpineSprite


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	_vp = SubViewport.new()
	_vp.size = Vector2i(1860, 2580)
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
	_sprite.update_mode = SpineConstant.UpdateMode_Manual
	_vp.add_child(_sprite)
	var scale_f := 2.88
	_sprite.scale = Vector2(scale_f, scale_f)
	_sprite.position = Vector2(930.0 - 26.5 * scale_f, 60.0)

	var st := _sprite.get_animation_state()
	var sk := _sprite.get_skeleton()
	print("slots=", sk.get_slots().size())
	for mode in ["all", "solo_hand", "no_head", "no_hair_r", "no_hand"]:
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation("present", false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(0.9)
		st.update(0.0)
		match mode:
			"solo_hand":
				_alpha_all(sk, 0.0, ["hand_r_front"])
			"no_head":
				_alpha_all(sk, 1.0, [], ["head", "eyes", "mouth"])
			"no_hair_r":
				_alpha_all(sk, 1.0, [], ["hair_r", "hair_l"])
			"no_hand":
				_alpha_all(sk, 1.0, [], ["hand_r_front"])
		_sprite.update_skeleton(0.0)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := _vp.get_texture().get_image()
		img.save_png(OUT + "/" + mode + ".png")
		print("saved ", mode, " bbox=", img.get_used_rect())
	get_tree().quit()


func _alpha_all(sk: SpineSkeleton, base: float, keep: Array, hide: Array = []) -> void:
	var slots = sk.get_slots()
	for i in slots.size():
		var sl = slots[i]
		var nm: String = sl.get_data().get_name()
		var a := base
		if keep.has(nm):
			a = 1.0
		if hide.has(nm):
			a = 0.0
		var c: Color = sl.get_color()
		c.a = a
		sl.set_color(c)
