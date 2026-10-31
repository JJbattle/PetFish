extends Node
## Dev-only: render the hand_open attachment alone in the setup pose, then
## with the present-pose bone angles, to check the art and its placement.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/hand_art"

const KEEP := ["hand_r"]

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

	var sk := _sprite.get_skeleton()
	var all := []
	var slot_count := sk.get_slots().size()
	for i in slot_count:
		all.append(sk.get_slots()[i].get_data().get_name())

	for mode in ["rest", "pose"]:
		sk.set_to_setup_pose()
		for s in all:
			if not KEEP.has(s):
				sk.set_attachment(s, "")
		sk.set_attachment("hand_r", "hand_open")
		if mode == "pose":
			sk.find_bone("armR1").set_rotation(-58.0)
			sk.find_bone("armR2").set_rotation(-24.0)
		_sprite.update_skeleton(0.0)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		_vp.get_texture().get_image().save_png(OUT + "/" + mode + ".png")
		var b := sk.find_bone("handR")
		print(mode, " handR=(%.0f,%.0f) rot=%.1f" % [b.get_world_x(), b.get_world_y(), b.get_rotation()])
	get_tree().quit()
