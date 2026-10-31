extends Node
## Dev-only: render candidate arm poses as *deltas* from setup (the same thing
## an animation key does) so a gesture can be picked by eye at real size.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/pose_probe"
## [name, d1, d2, both arms?, which side for one-arm poses]
const POSES := [
	["wide_a", -60.0, -40.0, true, "l"],
	["wide_b", -75.0, -55.0, true, "l"],
	["wide_c", -50.0, -55.0, true, "l"],
	["up_face", -100.0, -20.0, true, "l"],
	["alarm_face", -52.0, -104.0, true, "l"],
	["wave_l", -95.0, -25.0, false, "l"],
	["wave_r", -95.0, -25.0, false, "r"],
]


func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet pose_probe")
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	var pet = vp.get_child(0)
	pet.set_process(false)
	var rig: SpineSprite = pet._rig
	var st := rig.get_animation_state()
	st.clear_track(0)
	st.update(0.0)
	var sk = rig.get_skeleton()
	var base := {}
	for bn in ["armL1", "armL2", "armR1", "armR2"]:
		base[bn] = sk.find_bone(bn).get_rotation()
	for p in POSES:
		var d1 := float(p[1])
		var d2 := float(p[2])
		sk.set_to_setup_pose()
		if bool(p[3]) or str(p[4]) == "l":
			sk.find_bone("armL1").set_rotation(base["armL1"] + d1)
			sk.find_bone("armL2").set_rotation(base["armL2"] + d2)
		if bool(p[3]) or str(p[4]) == "r":
			sk.find_bone("armR1").set_rotation(base["armR1"] - d1)
			sk.find_bone("armR2").set_rotation(base["armR2"] - d2)
		rig.update_skeleton(0.0)
		var h = sk.find_bone("handR")
		var hl = sk.find_bone("handL")
		print("POSE ", p[0], " R=(%.1f,%.1f) L=(%.1f,%.1f)" % [
			h.get_world_x(), h.get_world_y(), hl.get_world_x(), hl.get_world_y()])
		var img := await Stage.grab(vp)
		Stage.save_png(img, OUT + "/" + str(p[0]) + ".png")
	Stage.ok("rendered %d poses" % POSES.size())
