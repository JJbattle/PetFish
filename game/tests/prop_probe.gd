extends Node
## Dev-only: attach one prop at a time in the setup pose to find bad meshes.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/prop_probe"

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
	var scale_f := 0.99
	_sprite.scale = Vector2(scale_f, scale_f)
	_sprite.position = Vector2(310.0 - 26.5, 20.0)

	var cases := [
		["00_none", "", ""],
		["01_cup", "cup", "bottle"],
		["02_water", "water", "water"],
		["03_grip_r", "cup_hand_r", "hand_grip"],
		["04_grip_l", "cup_hand_l", "hand_grip_l"],
		["05_book", "book", "book"],
		["06_pen", "pen", "pen"],
		["07_fish", "fish", "fish"],
		["08_fish_tail", "fish_tail", "fish_tail"],
		["09_hand_open", "hand_r", "hand_open"],
	]
	var sk := _sprite.get_skeleton()
	for c in cases:
		var label: String = c[0]
		var slot_name: String = c[1]
		var att_name: String = c[2]
		sk.set_to_setup_pose()
		if slot_name != "":
			sk.set_attachment(slot_name, att_name)
		_sprite.update_skeleton(0.0)
		if slot_name != "":
			var sl := sk.find_slot(slot_name)
			print("  worldPos=", sl.get_bone().get_world_x(), ",", sl.get_bone().get_world_y())
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := _vp.get_texture().get_image()
		img.save_png(OUT + "/" + label + ".png")
		print("saved ", label, " bbox=", img.get_used_rect())
	get_tree().quit()
