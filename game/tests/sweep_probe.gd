extends Node
## Dev-only: sweep *delta* rotations (setup + delta, exactly what an animation
## key does) so poses can be tuned against where the hands really land.

const Stage = preload("res://tests/test_stage.gd")


func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet sweep_probe")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	var pet = vp.get_child(0)
	var rig: SpineSprite = pet._rig
	var st := rig.get_animation_state()
	st.clear_track(0)
	st.update(0.0)
	var sk = rig.get_skeleton()
	var base := {}
	for bn in ["armL1", "armL2", "armR1", "armR2"]:
		base[bn] = sk.find_bone(bn).get_rotation()
	print("setup ", base)
	for d1 in [-40.0, -60.0, -80.0, -100.0, -120.0]:
		for d2 in [0.0, -20.0, -40.0, 20.0]:
			sk.set_to_setup_pose()
			sk.find_bone("armL1").set_rotation(base["armL1"] + d1)
			sk.find_bone("armL2").set_rotation(base["armL2"] + d2)
			sk.find_bone("armR1").set_rotation(base["armR1"] - d1)
			sk.find_bone("armR2").set_rotation(base["armR2"] - d2)
			rig.update_skeleton(0.0)
			var hl = sk.find_bone("handL")
			var hr = sk.find_bone("handR")
			print("d1=%6.1f d2=%6.1f  L=(%6.1f,%6.1f)  R=(%6.1f,%6.1f)" % [
				d1, d2, hl.get_world_x(), hl.get_world_y(),
				hr.get_world_x(), hr.get_world_y()])
	print("--- head reference")
	sk.set_to_setup_pose()
	rig.update_skeleton(0.0)
	for bn in ["head", "handL", "handR", "chest"]:
		var b = sk.find_bone(bn)
		print(bn, " (", b.get_world_x(), ",", b.get_world_y(), ")")
	Stage.ok("sweep printed")
