extends Node
## Dev-only: sweep the wrist roll in the held side-present pose, one PNG per
## value, so the palm can be turned up without rebuilding the rig each time.
##
## The clip is played normally (slots, attachments, turn all real); the hand's
## setup rotation is then overridden and the sprite re-solved, which is safe
## because these clips key the wrist at 0.
## Run: godot --path game --rendering-driver opengl3 res://tests/arm_lab.tscn
## Output: tools/_debug/lab/hand_<deg>.png

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/lab"
const CLIP := "present"
const VALUES := [-120.0, -90.0, -60.0, -30.0, 0.0, 30.0, 60.0, 90.0, 120.0]


func _ready() -> void:
	Stage.begin(self, 120.0, "FishPet arm_lab")
	DirAccess.make_dir_recursive_absolute(OUT)
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	var pet = vp.get_child(0)
	pet.set_process(false)
	for child in pet.get_children():
		if child != pet._rig and child is CanvasItem:
			child.hide()
	var rig: SpineSprite = pet._rig
	var sk = rig.get_skeleton()
	var st := rig.get_animation_state()
	for v in VALUES:
		st.clear_track(0)
		st.set_animation(CLIP, false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(1.5)
		st.update(0.0)
		sk.find_bone("handR").set_rotation(float(v))
		rig.update_skeleton(0.0)
		var hb = sk.find_bone("handR")
		print("HAND %6.1f world=(%6.1f,%6.1f) wrot=%6.1f" % [v,
			hb.get_world_x(), hb.get_world_y(), hb.get_world_rotation_x()])
		var img := await Stage.grab(vp)
		Stage.save_png(img, OUT + "/hand_%d.png" % int(v))
	Stage.ok("swept %d wrist angles" % VALUES.size())
