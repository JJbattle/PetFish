extends Node
## Dev-only: hold a static bone pose (no animation state) and isolate slots.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/iso"

const POSE := {
	"armL1": 0.0, "armL2": 0.0, "armR1": 0.0, "armR2": 0.0,
	"head": 0.0, "chest_scale": 1.0,
}

var vp: SubViewport
var sprite: SpineSprite


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	vp = SubViewport.new()
	vp.size = Vector2i(600, 840)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	sprite = SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.position = Vector2(300, 10)
	vp.add_child(sprite)

	var cases := {
		"hide_body": ["body"],
		"hide_skirt": ["skirt"],
		"only_body": ["head", "hair_l", "hair_r", "tail", "skirt", "cup",
				"arm_up_l", "arm_up_r", "arm_fore_l", "arm_fore_r", "hand_l", "hand_r"],
	}
	for key in cases:
		sprite.get_skeleton().set_to_setup_pose()
		apply_pose()
		var sk := sprite.get_skeleton()
		for s in cases[key]:
			sk.find_slot(s).set_attachment(null)
		sprite.update_skeleton(0.0)
		var live := []
		for slot in sk.get_draw_order():
			var a = slot.get_attachment()
			if a != null:
				live.append(a.get_attachment_name())
		print("CASE ", key, " ", live)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		vp.get_texture().get_image().save_png(OUT + "/iso_" + key + ".png")
	print("done")
	get_tree().quit()


func apply_pose() -> void:
	return
	var sk := sprite.get_skeleton()
	for name in ["armL1", "armL2", "armR1", "armR2", "head"]:
		var b = sk.find_bone(name)
		b.set_rotation(POSE[name])
	sk.find_bone("chest").set_scale_x(POSE["chest_scale"])
	sk.find_bone("chest").set_scale_y(POSE["chest_scale"])
