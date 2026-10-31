extends Node
## Dev-only: inspect draw order after applying a clip.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"

var sprite: SpineSprite


func _ready() -> void:
	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	sprite = SpineSprite.new()
	sprite.skeleton_data_res = data
	add_child(sprite)

	var methods := []
	for m in ClassDB.class_get_method_list("SpineSkeleton", true):
		methods.append(m.name)
	print("SKELETON_METHODS ", methods)

	var st := sprite.get_animation_state()
	for anim in ["idle", "cheer", "stretch", "needs_input"]:
		var sk := sprite.get_skeleton()
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation(anim, false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(0.6)
		st.update(0.0)
		sprite.update_skeleton(0.0)
		var names := []
		for s in sk.get_slots():
			var a = s.get_attachment()
			names.append(a.get_attachment_name() if a != null else "-")
		print("ORDER ", anim, " attach=", names)
		var dnames := []
		for s in sk.get_draw_order():
			var a = s.get_attachment()
			dnames.append(a.get_attachment_name() if a != null else "-")
		print("DRAW ", anim, " attach=", dnames)
	get_tree().quit()
