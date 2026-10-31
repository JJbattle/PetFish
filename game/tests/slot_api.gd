extends Node
const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"

var _vp: SubViewport
var _sprite: SpineSprite

func _ready() -> void:
	_vp = SubViewport.new()
	_vp.size = Vector2i(64, 64)
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
	var st := _sprite.get_animation_state()
	var sk := _sprite.get_skeleton()
	sk.set_to_setup_pose()
	st.set_animation("drink_sip", false, 0.0)
	st.update(0.0)
	var cur := st.get_current(0)
	cur.set_track_time(0.45)
	st.update(0.0)
	_sprite.update_skeleton(0.0)
	_show(sk, "after anim")
	sk.set_attachment("cup", "")
	_show(sk, "after hide cup")
	_sprite.update_skeleton(0.0)
	_show(sk, "after update_skeleton")
	await get_tree().process_frame
	_show(sk, "after process frame")
	_sprite.update_skeleton(0.0)
	print("att by name empty ->", sk.get_attachment_by_slot_name("cup", ""))
	get_tree().quit()

func _show(sk: SpineSkeleton, tag: String) -> void:
	var att := sk.find_slot("cup").get_attachment()
	print(tag, ": cup att=", "<none>" if att == null else att.get_attachment_name())
