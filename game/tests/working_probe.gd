extends Node
## Dev-only: render the working pose with the props hidden, to inspect arms.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/working_probe"

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
	_sprite.position = Vector2(283.5, 20.0)

	var st := _sprite.get_animation_state()
	var sk := _sprite.get_skeleton()
	var cases := [
		["00_all", []],
		["01_nobottle", ["cup"]],
		["02_nohand_l", ["hand_l"]],
		["03_nosleeve_r", ["arm_up_r", "arm_fore_r"]],
		["04_nohead", ["head"]],
		["05_nohair", ["hair_l", "hair_r"]],
		["06_noskirt", ["skirt"]],
		["07_nobody", ["body"]],
	]
	for c in cases:
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation("working", false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(0.45)
		st.update(0.0)
		_sprite.update_skeleton(0.0)
		for sl in c[1]:
			sk.set_attachment(sl, "")
		var names := []
		for sn in SLOTS:
			var s := sk.find_slot(sn)
			var at := s.get_attachment()
			if at != null:
				names.append("%s=%s" % [sn, at.get_attachment_name()])
		print(c[0], " ", " ".join(names))
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		_vp.get_texture().get_image().save_png(OUT + "/" + c[0] + ".png")
	get_tree().quit()
