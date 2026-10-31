extends Node
## Dev-only: apply drink_sip, list what each slot has attached, then render
## once per hidden slot to find which attachment draws the stray quads.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/slot_probe"

const SLOTS := ["hair_l", "hair_r", "body", "skirt", "tail", "arm_up_l", "arm_up_r",
	"arm_fore_l", "arm_fore_r", "book", "fish_tail", "fish", "hand_l", "hand_r",
	"pen", "head", "eyes", "mouth", "water", "cup", "cup_hand_l", "cup_hand_r"]

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
	_sprite.position = Vector2(310.0 - 26.5, 20.0)

	var st := _sprite.get_animation_state()
	var sk := _sprite.get_skeleton()
	sk.set_to_setup_pose()
	st.clear_track(0)
	st.set_animation("drink_sip", false, 0.0)
	st.update(0.0)
	var cur := st.get_current(0)
	cur.set_track_time(0.45)
	st.update(0.0)
	_sprite.update_skeleton(0.0)

	for name in SLOTS:
		var sl := sk.find_slot(name)
		var att := sl.get_attachment()
		if att == null:
			print("%-12s <none>" % name)
		else:
			print("%-12s %s" % [name, att.get_attachment_name()])
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	_vp.get_texture().get_image().save_png(OUT + "/00_all.png")

	for hide in ["hair_l", "hair_r", "body", "skirt", "tail", "arm_up_l", "arm_up_r",
			"arm_fore_l", "arm_fore_r", "head"]:
		sk.set_attachment(hide, "")
		_sprite.update_skeleton(0.0)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		_vp.get_texture().get_image().save_png(OUT + "/hide_" + hide + ".png")
		print("saved hide_", hide)
	get_tree().quit()
