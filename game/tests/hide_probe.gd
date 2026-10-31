extends Node
## Dev-only: hide one slot via colour alpha (not the attachment) and render
## the drink pose, to find which layer leaves the white gap.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/hide_probe"

var _vp: SubViewport
var _sprite: SpineSprite


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	_vp = SubViewport.new()
	_vp.size = Vector2i(620, 860)
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
	_sprite.scale = Vector2(0.99, 0.99)
	_sprite.position = Vector2(283.5, 20.0)

	var st := _sprite.get_animation_state()
	var sk := _sprite.get_skeleton()
	var cases := ["", "hair_r", "hair_l", "body", "skirt", "head", "arm_fore_r", "arm_up_r"]
	for hide in cases:
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation("drink_sip", false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(0.45)
		st.update(0.0)
		_sprite.update_skeleton(0.0)
		if hide != "":
			var sl := sk.find_slot(hide)
			var c := sl.get_color()
			c.a = 0.0
			sl.set_color(c)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var label: String = "00_all" if hide == "" else hide
		_vp.get_texture().get_image().save_png(OUT + "/" + label + ".png")
		print("saved ", label)
	get_tree().quit()
