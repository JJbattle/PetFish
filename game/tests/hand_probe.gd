extends Node
## Dev-only: isolate which slot paints the pale shards at the presented hand.
## Renders the present pose normally, then with hand_r removed and with
## arm_fore_r removed.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/hand_probe"

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
	_sprite.scale = Vector2(0.96, 0.96)
	_sprite.position = Vector2(310.0 - 26.5 * 0.96, 20.0)

	var st := _sprite.get_animation_state()
	var sk := _sprite.get_skeleton()
	for mode in ["all", "nohand", "nofore", "noupper", "noprop"]:
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation("present", false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(0.9)
		st.update(0.0)
		_sprite.update_skeleton(0.0)
		match mode:
			"nohand":
				sk.set_attachment("hand_r", "")
			"nofore":
				sk.set_attachment("arm_fore_r", "")
			"noupper":
				sk.set_attachment("arm_up_r", "")
			"noprop":
				for s in ["hand_r", "arm_fore_r", "arm_up_r"]:
					sk.set_attachment(s, "")
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		_vp.get_texture().get_image().save_png(OUT + "/" + mode + ".png")
		print("saved ", mode)
	get_tree().quit()
