extends Node
## Dev-only: render one setup-pose slot at a time (hides work without a clip).

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/body_probe"

const ALL := ["hair_l", "hair_r", "skirt", "tail", "arm_up_l", "arm_up_r",
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

	var sk := _sprite.get_skeleton()
	for keep in ["body", "skirt", "head", "hair_r"]:
		sk.set_to_setup_pose()
		for s in ALL:
			if s != keep:
				sk.set_attachment(s, "")
		_sprite.update_skeleton(0.0)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		_vp.get_texture().get_image().save_png(OUT + "/" + keep + ".png")
		print("saved ", keep)
	get_tree().quit()
