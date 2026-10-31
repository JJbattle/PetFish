extends Node
## Dev-only: capture the four key poses of the two-handed 250 ml drink and print
## bone world positions so the IK can be checked numerically.
##
## Poses: 捧杯 (hold) -> 贴嘴 (rim to lips) -> 喝水 (sip) -> 放杯 (lower).
## Run: Godot --path game res://tests/drink_pose.tscn --resolution 600x840

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/drink250_v2"

const POSES := [
	["key_00_hold", "drink_in", 0.5],
	["key_01_rim", "drink_in", 0.85],
	["key_02_sip", "drink_sip", 0.45],
	["key_03_lower", "drink_out", 0.55],
	["key_04_sip3", "drink_sip3", 0.9],
]

var _vp: SubViewport
var _sprite: SpineSprite


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	_vp = SubViewport.new()
	_vp.size = Vector2i(600, 840)
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
	# stop the sprite's own process update from advancing past the probed time
	# while we await the frame capture
	_sprite.update_mode = SpineConstant.UpdateMode_Manual
	_vp.add_child(_sprite)

	var win := Vector2(600, 840)
	var scale_f := minf(win.x * 0.9 / 599.0, (win.y - 90.0) / 820.0)
	_sprite.scale = Vector2(scale_f, scale_f)
	_sprite.position = Vector2(win.x * 0.5 - 26.5 * scale_f, 40.0)
	print("scale=", scale_f)

	# reference: the untouched setup pose (no cup, hands at the sides)
	var sk := _sprite.get_skeleton()
	sk.set_to_setup_pose()
	_sprite.update_skeleton(0.0)
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	_vp.get_texture().get_image().save_png(OUT + "/key_00_rest.png")
	print("saved key_00_rest")

	var st := _sprite.get_animation_state()
	for pose in POSES:
		var label: String = pose[0]
		var anim: String = pose[1]
		var t: float = pose[2]
		sk = _sprite.get_skeleton()
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation(anim, false, 0.0)
		st.update(0.0)
		var cur := st.get_current(0)
		if cur != null:
			cur.set_track_time(t)
		st.update(0.0)
		_sprite.update_skeleton(0.0)
		_print_bones(label)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := _vp.get_texture().get_image()
		img.save_png(OUT + "/" + label + ".png")
		print("saved ", label, " bbox=", img.get_used_rect())
	get_tree().quit()


func _print_bones(label: String) -> void:
	var sk := _sprite.get_skeleton()
	var w := func(n: String) -> String:
		var bone := sk.find_bone(n)
		return "%s=(%.1f,%.1f)r=%.1f" % [n, bone.get_world_x(), bone.get_world_y(), bone.get_rotation()]
	print("POSE ", label)
	print("  ", w.call("cup"))
	print("  ", w.call("gripL"), "   ", w.call("gripR"))
	print("  ", w.call("handL"), "   ", w.call("handR"))
	print("  shL ", w.call("armL1"), "  elL ", w.call("armL2"))
	print("  shR ", w.call("armR1"), "  elR ", w.call("armR2"))
	print("  ", w.call("head"))
	# grip error = distance from each hand to its grip target (should be ~0)
	var hL := sk.find_bone("handL")
	var hR := sk.find_bone("handR")
	var gL := sk.find_bone("gripL")
	var gR := sk.find_bone("gripR")
	print("  gripErrL=%.2f  gripErrR=%.2f" % [
		Vector2(hL.get_world_x() - gL.get_world_x(), hL.get_world_y() - gL.get_world_y()).length(),
		Vector2(hR.get_world_x() - gR.get_world_x(), hR.get_world_y() - gR.get_world_y()).length()])
