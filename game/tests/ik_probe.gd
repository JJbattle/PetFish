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
	for c in [["setup", "", 0.0], ["working", "working", 0.0],
			["working2", "working", 1.0], ["drink", "drink_sip", 0.45],
			["slack", "slack", 1.0]]:
		sk.set_to_setup_pose()
		st.clear_track(0)
		if c[1] != "":
			st.set_animation(c[1], false, 0.0)
			st.update(0.0)
			var cur := st.get_current(0)
			cur.set_track_time(c[2])
			st.update(0.0)
		_sprite.update_skeleton(0.0)
		var parts := []
		for n in ["armL1", "armL2", "handL", "armR1", "armR2", "handR", "gripL", "gripR", "workL", "workR", "slackR"]:
			var b := sk.find_bone(n)
			parts.append("%s(%.0f,%.0f)" % [n, b.get_world_x(), b.get_world_y()])
		var iks := []
		for n in ["ik_arm_l", "ik_work_l", "ik_slack_l"]:
			var c2 := sk.find_ik_constraint(n)
			iks.append("%s mix=%.2f" % [n, c2.get_mix() if c2 else -1.0])
		print(c[0], " ", " ".join(parts))
		print("   ", " ".join(iks))
	get_tree().quit()
