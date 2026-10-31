extends Node
## Dev-only: print where the wrists actually land for a clip at a given time,
## next to the IK target they are supposed to reach.  Used to place the whale
## hold and to catch a wrist that the arm chain cannot reach.
##
## Run: godot --path game --rendering-driver opengl3 res://tests/bone_probe.tscn
##      -- slack:0.5,slack_in:0.66,present2:1.5

const Stage = preload("res://tests/test_stage.gd")
const BONES := ["fish", "slackL", "slackR", "handL", "handR",
	"armL1", "armL2", "armR1", "armR2"]


func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet bone_probe")
	var vp := Stage.make_stage(self, Vector2i(380, 480))
	await Stage.settled()
	var pet = vp.get_child(0)
	pet.set_process(false)
	var rig: SpineSprite = pet._rig
	var st := rig.get_animation_state()
	var sk = rig.get_skeleton()
	var args := OS.get_cmdline_user_args()
	var items := String(args[0] if args.size() > 0 else "slack:0.5").split(",", false)
	for item in items:
		var parts := String(item).split(":", false, 1)
		var anim := parts[0]
		var t := float(parts[1]) if parts.size() > 1 else 0.0
		sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation(anim, false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(t)
		st.update(0.0)
		rig.update_skeleton(0.0)
		print("--- ", anim, " @ ", t)
		for bn in BONES:
			var b = sk.find_bone(bn)
			if b == null:
				print("  %-7s MISSING" % bn)
				continue
			print("  %-7s world=(%7.2f,%7.2f) rot=%7.2f applied=%7.2f len=%6.2f" % [
				bn, b.get_world_x(), b.get_world_y(),
				b.get_rotation(), b.get_applied_rotation(),
				b.get_data().get_length()])
	Stage.ok("bone probe done")
