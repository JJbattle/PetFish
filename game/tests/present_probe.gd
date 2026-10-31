extends Node
## Dev-only: present pose with the hair and tail lifted, so the offered arm and
## hand can be seen and tuned.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/present_probe"

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
	for t in [0.0, 0.9, 1.8]:
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation("present", false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(t)
		st.update(0.0)
		_sprite.update_skeleton(0.0)
		for hide in ["", "hair", "tail"]:
			if hide == "hair":
				for s in ["hair_l", "hair_r", "hair_back"]:
					sk.set_attachment(s, "")
			elif hide == "tail":
				sk.set_attachment("tail", "")
			await get_tree().process_frame
			await RenderingServer.frame_post_draw
			await RenderingServer.frame_post_draw
			var name := "present_t%.1f_%s.png" % [t, hide if hide != "" else "all"]
			_vp.get_texture().get_image().save_png(OUT + "/" + name)
			print("saved ", name)
		var parts := []
		for n in ["armL1", "armL2", "handL", "armR1", "armR2", "handR"]:
			var b := sk.find_bone(n)
			parts.append("%s(%.0f,%.0f,r%.0f)" % [n, b.get_world_x(), b.get_world_y(), b.get_rotation()])
		print("t=%.1f " % t, " ".join(parts))
	get_tree().quit()
