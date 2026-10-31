extends Node
## Dev-only: the open palm alone, at a set of wrist rolls, rendered large.
## The hand is ~20 px on screen in the real overlay, so judging "which angle
## points the fingers at the card" from a full-body shot is guesswork.
##
## Run: godot --path game --rendering-driver opengl3 res://tests/hand_pose_probe.tscn
## Output: tools/_debug/hand_pose/<deg>.png

const SKEL := "res://assets/pet_spine/pet.spine-json"
const ATLAS := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/hand_pose"
const VALUES := [-180.0, -135.0, -90.0, -45.0, 0.0, 45.0, 90.0, 135.0]
const SLOTS := ["hair_back", "hair_l", "hair_r", "body", "skirt", "tail",
	"arm_up_l", "arm_up_r", "arm_fore_l", "arm_fore_r", "book", "fish",
	"hand_l", "hand_r", "pen", "pen_hand", "head", "eyes", "mouth", "water",
	"cup", "cup_hand_l", "cup_hand_r", "fish_hand_l", "fish_hand_r",
	"arm_fore_l_front", "arm_fore_r_front", "hand_l_front", "hand_r_front"]


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := SubViewport.new()
	vp.size = Vector2i(420, 420)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)

	var sf: SpineSkeletonFileResource = load(SKEL)
	var atlas: SpineAtlasResource = load(ATLAS)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()

	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.update_mode = SpineConstant.UpdateMode_Manual
	vp.add_child(sprite)
	# the skeleton lives in source coords shifted by (-470,-132): handR is at
	# (132,531) here, and that is what has to land in the middle
	sprite.scale = Vector2(3.0, 3.0)
	sprite.position = Vector2(210.0, 210.0) - Vector2(132.0, 531.0) * 3.0

	var sk := sprite.get_skeleton()
	for v in VALUES:
		sk.set_to_setup_pose()
		for s in SLOTS:
			sk.set_attachment(s, "")
		sk.set_attachment("hand_r_front", "hand_open")
		sk.set_attachment("arm_fore_r_front", "arm_fore_r")
		sk.find_bone("handR").set_rotation(deg_to_rad(v))
		print("DBG bone=", sk.find_bone("handR").get_world_x(), ",", sk.find_bone("handR").get_world_y())
		sprite.update_skeleton(0.0)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := vp.get_texture().get_image()
		img.save_png(OUT + "/h%+.0f.png" % v)
		print("saved ", v)
	get_tree().quit()
