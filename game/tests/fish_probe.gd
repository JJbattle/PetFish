extends Node
## Dev-only: pose `slack` and move the fish bone around to find out whether the
## whale attachment is drawn at all.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/fish_probe"


func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet fish_probe")
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	var pet = vp.get_child(0)
	pet.set_process(false)
	var rig: SpineSprite = pet._rig
	var st := rig.get_animation_state()
	var cases := [
		["base", 0.0, 0.0],
		["right", 260.0, 0.0],
		["up", 0.0, -200.0],
	]
	for c in cases:
		rig.get_skeleton().set_to_setup_pose()
		st.clear_track(0)
		st.set_animation("slack", false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(0.5)
		st.update(0.0)
		var sk := rig.get_skeleton()
		var bone = sk.find_bone("fish")
		bone.get_parent().update_world_transform()
		bone.set_x(float(c[1]))
		bone.set_y(float(c[2]))
		rig.update_skeleton(0.0)
		print("CASE ", c[0], " fish world=", bone.get_world_x(), ",", bone.get_world_y(),
			" att=", sk.find_slot("fish").get_attachment())
		var img := await Stage.grab(vp)
		Stage.save_png(img, OUT + "/" + str(c[0]) + ".png")
		print("  bbox=", img.get_used_rect())
	Stage.ok("rendered %d fish poses" % cases.size())
