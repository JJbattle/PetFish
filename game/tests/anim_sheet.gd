extends Node
## Dev-only: capture one key pose from every clip for visual review.
##
## Run: Godot --path game res://tests/anim_sheet.tscn --resolution 620x860

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/anim_sheet"

const POSES := [
	["00_rest", "idle", 0.0],
	["01_idle_left", "idle", 0.95],
	["02_idle_right", "idle", 3.75],
	["03_working", "working", 0.45],
	["04_working_pause", "working", 2.0],
	["05_slack", "slack", 1.3],
	["06_present", "present", 0.5],
	["06b_present2", "present2", 0.9],
	["06c_present_in", "present_in", 0.42],
	["06d_present_out", "present_out", 0.22],
	["06e_present2_in", "present2_in", 0.48],
	["07_water_remind", "water_remind", 1.2],
	["08_drink_in", "drink_in", 0.85],
	["09_drink_sip", "drink_sip", 0.45],
	["10_drink_sip3", "drink_sip3", 0.45],
	["11_drink_out", "drink_out", 0.55],
	["12_hop_air", "hop_sit", 0.30],
	["13_hop_land", "hop_sit", 0.56],
	["14_needs_wave", "needs_input", 1.0],
	["15_cheer", "cheer", 0.55],
	["16_stretch", "stretch", 1.6],
]

var _vp: SubViewport
var _sprite: SpineSprite


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	# SHEET_SCALE=3 renders the same sheet three times as large for close-up
	# review of hands and faces (the poses and camera framing are identical).
	var sheet_scale := float(OS.get_environment("SHEET_SCALE")) if \
		OS.get_environment("SHEET_SCALE") != "" else 1.0
	var win := Vector2(620, 860) * sheet_scale
	_vp = SubViewport.new()
	_vp.size = Vector2i(win)
	_vp.transparent_bg = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	print("loaded=", data.is_skeleton_data_loaded())

	_sprite = SpineSprite.new()
	_sprite.skeleton_data_res = data
	_sprite.update_mode = SpineConstant.UpdateMode_Manual
	_vp.add_child(_sprite)

	var scale_f := minf(win.x * 0.96 / 599.0, (win.y - 40.0 * sheet_scale) / 820.0)
	_sprite.scale = Vector2(scale_f, scale_f)
	_sprite.position = Vector2(win.x * 0.5 - 26.5 * scale_f, 20.0 * sheet_scale)

	var st: SpineAnimationState = _sprite.get_animation_state()
	for pose in POSES:
		var label: String = pose[0]
		var anim: String = pose[1]
		var t: float = pose[2]
		var sk := _sprite.get_skeleton()
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation(anim, false, 0)
		st.update(0.0)
		var cur := st.get_current(0)
		if cur != null:
			cur.set_track_time(t)
		st.update(0.0)
		_sprite.update_skeleton(0.0)
		if label.begins_with("09") or label.begins_with("10") or label.begins_with("11"):
			_print_grip(label)
		if label.begins_with("06") or label.begins_with("00"):
			_print_hand(label)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := _vp.get_texture().get_image()
		img.save_png(OUT + "/" + label + ".png")
		print("saved ", label, " bbox=", img.get_used_rect())
	get_tree().quit()


func _print_hand(label: String) -> void:
	var sk := _sprite.get_skeleton()
	for tag in ["handR", "handL"]:
		var b := sk.find_bone(tag)
		var deg := atan2(b.get_world_rotation_y(), b.get_world_rotation_x()) * 180.0 / PI
		print("HAND ", label, " ", tag, " worldRot=%.1f" % deg,
			" head=%.1f,%.1f" % [b.get_world_x(), b.get_world_y()])


func _print_grip(label: String) -> void:
	var sk := _sprite.get_skeleton()
	var hL := sk.find_bone("handL")
	var hR := sk.find_bone("handR")
	var gL := sk.find_bone("gripL")
	var gR := sk.find_bone("gripR")
	var hd := sk.find_bone("head")
	print("POSE ", label,
		" gripErrL=%.2f gripErrR=%.2f" % [
			Vector2(hL.get_world_x() - gL.get_world_x(),
				hL.get_world_y() - gL.get_world_y()).length(),
			Vector2(hR.get_world_x() - gR.get_world_x(),
				hR.get_world_y() - gR.get_world_y()).length()],
		" headRot=%.1f worldRot=%.1f" % [hd.get_rotation(),
			atan2(hd.get_world_rotation_y(), hd.get_world_rotation_x()) * 180.0 / PI])
