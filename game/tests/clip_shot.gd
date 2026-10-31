extends Node
## Dev-only: pose clips at chosen times and save a PNG per pose, so props and
## gestures can be checked at the size the user sees; `clip:all` renders the
## whole clip frame by frame at 24 fps so the motion can be reviewed too.
##
## Run (engine options before the scene, scene args after --):
##   godot --path game --rendering-driver opengl3 res://tests/clip_shot.tscn \
##       -- drink_in:0.4,drink_in:0.8,working_in:all
## Output: tools/_debug/clip_shot/<clip>_<time>.png
##         tools/_debug/clip_shot/seq/<clip>_<frame>.png  (clip:all)
##
## Renders into a SubViewport and drives a normal, non-topmost window (see
## test_stage.gd); bad clip names exit non-zero instead of saving nothing.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/clip_shot"
const FPS := 24.0
const ALL := -2.0
## spine-godot's update_mode hint is "Process,Physics,Manual"; the enum itself
# is not exposed to script, so the value is spelled out here
const UPDATE_MANUAL := 2

var _dir := OUT


func _ready() -> void:
	Stage.begin(self, 300.0, "FishPet clip_shot")
	# FISHPET_SHOT_DIR keeps a 50 % render pass from overwriting the full-size
	# one, which is how the two sizes are compared side by side
	var sub := OS.get_environment("FISHPET_SHOT_DIR")
	if sub != "":
		_dir = OUT + "/" + sub
	else:
		_dir = OUT
	var wanted := _parse_args()
	if wanted.is_empty():
		Stage.die("no clips requested; pass clip[:time|:all] after --")
		return
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	await Stage.settled()
	var pet = vp.get_child(0)
	pet.set_process(false)
	# the pose is applied by hand below; a sprite that keeps updating itself
	# advances the clip's own timeline between our set_track_time and the grab
	pet._rig.update_mode = UPDATE_MANUAL
	# Poses never need the bubble or the cards, and leaving them in poisons the
	# union silhouette built from these frames (a dark bar above the pet).
	for child in pet.get_children():
		if child != pet._rig and child is CanvasItem:
			child.hide()
	var rig: SpineSprite = pet._rig
	var data = rig.get_skeleton().get_data()
	var st := rig.get_animation_state()
	for item in wanted:
		var anim: String = item[0]
		if data.find_animation(anim) == null:
			Stage.die("no such clip: %s" % anim)
			return
	var shots := 0
	for item in wanted:
		var anim: String = item[0]
		var t: float = item[1]
		if t == ALL:
			var dur: float = data.find_animation(anim).get_duration()
			var frames := int(ceil(dur * FPS))
			for i in frames + 1:
				await _pose_and_save(rig, st, vp, anim, float(i) / FPS,
					_dir + "/seq", "%s_%03d" % [anim, i])
				shots += 1
			print("SEQ ", anim, " ", frames + 1, " frames @ ", FPS, " fps")
			continue
		# a bare clip name samples it at three points; "clip:time" poses exactly
		var times: Array = [t] if t >= 0.0 else [0.2, 0.6, 0.9]
		for step in times:
			var at: float = (step if t >= 0.0
				else float(step) * data.find_animation(anim).get_duration())
			await _pose_and_save(rig, st, vp, anim, at, _dir)
			shots += 1
	Stage.ok("rendered %d pose(s) to %s" % [shots, _dir])


func _pose_and_save(rig: SpineSprite, st, vp: SubViewport, anim: String, t: float,
		dir := OUT, label := "") -> void:
	rig.get_skeleton().set_to_setup_pose()
	st.clear_track(0)
	st.set_animation(anim, false, 0.0)
	st.update(0.0)
	st.get_current(0).set_track_time(t)
	st.update(0.0)
	rig.update_skeleton(0.0)
	if label == "":
		label = "%s_%.2f" % [anim, t]
		print("POSE ", anim, " %.2f" % t,
			" armL1=", rig.get_skeleton().find_bone("armL1").get_rotation(),
			" armL2=", rig.get_skeleton().find_bone("armL2").get_rotation(),
			" handR=", rig.get_skeleton().find_bone("handR").get_world_x(), ",",
			rig.get_skeleton().find_bone("handR").get_world_y())
	var img := await Stage.grab(vp)
	Stage.save_png(img, dir + "/" + label + ".png")


## "clip:time,clip:time,clip:all" -> [[clip, time], ...]; a bare "clip" samples
## the whole animation at three points.  Anything malformed is fatal.
func _parse_args() -> Array:
	var args := OS.get_cmdline_user_args()
	var out: Array = []
	if args.is_empty():
		return out
	for item in String(args[0]).split(",", false):
		var parts := String(item).split(":", false, 1)
		if parts.size() == 1:
			out.append([parts[0], -1.0])
			continue
		if parts.size() != 2:
			Stage.die("expected clip[:time|:all], got '%s'" % item)
			return []
		if parts[1] == "all":
			out.append([parts[0], ALL])
			continue
		if not parts[1].is_valid_float():
			Stage.die("time is not a number: '%s'" % item)
			return []
		out.append([parts[0], float(parts[1])])
	return out
