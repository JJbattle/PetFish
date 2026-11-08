extends Node
## Isolated renderer for the standalone activity rigs (see tools/activity_preview.py).
## Loads activity_standing / activity_seated and renders either a list of posed
## single frames (`poses`) or a true continuous loop (`loop`).  The loop mode is
## what the review asked for: it sets the animation ONCE with loop=true and steps
## the SAME animation state forward by a fixed dt every frame, so the clip really
## crosses its 2s/4s wrap boundaries instead of re-setting setup per sample.
## Every capture also dumps the piece-bone world positions so the skeleton's
## coordinate convention can be verified against prepare_activity_kit.py.

var _rig: SpineSprite


func _ready() -> void:
	get_window().always_on_top = false
	get_window().unfocusable = true
	get_window().mode = Window.MODE_MINIMIZED
	Engine.max_fps = 60
	var timer := Timer.new()
	timer.one_shot = true
	timer.wait_time = 90.0
	timer.timeout.connect(func(): get_tree().quit(3))
	add_child(timer)
	timer.start()

	var request = JSON.parse_string(FileAccess.get_file_as_string("res://request.json"))
	var scale: float = float(request.get("scale", 1.0))
	var vp_size := Vector2i(int(request.vp[0]), int(request.vp[1]))
	var vp := SubViewport.new()
	vp.size = vp_size
	vp.transparent_bg = true
	vp.disable_3d = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)

	var base := String(request.rig)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = load("res://assets/%s.spine-json" % base)
	data.atlas_res = load("res://assets/%s.atlas" % base)
	data.update_skeleton_data()
	if not data.is_skeleton_data_loaded():
		printerr("activity_preview: skeleton data failed to load")
		get_tree().quit(2)
		return
	_rig = SpineSprite.new()
	_rig.skeleton_data_res = data
	_rig.update_mode = 2
	_rig.position = Vector2.ZERO
	_rig.scale = Vector2(scale, scale)
	vp.add_child(_rig)
	await get_tree().process_frame

	var state := _rig.get_animation_state()
	var skeleton := _rig.get_skeleton()
	if request.has("loop"):
		await _run_loop(request, vp, state, skeleton)
	else:
		await _run_poses(request, vp, state, skeleton)
	get_tree().quit()


func _run_poses(request: Dictionary, vp: SubViewport, state, skeleton) -> void:
	var records := []
	for spec in String(request.poses).split(",", false):
		var parts := spec.split(":")
		var clip := parts[0]
		var t := float(parts[1]) if parts.size() > 1 else 0.0
		if clip == "setup":
			skeleton.set_to_setup_pose()
			_rig.update_skeleton(0.0)
		else:
			if skeleton.get_data().find_animation(clip) == null:
				printerr("Missing animation: ", clip)
				get_tree().quit(2)
				return
			skeleton.set_to_setup_pose()
			state.clear_track(0)
			state.set_animation(clip, false, 0)
			state.update(0.0)
			state.get_current(0).set_track_time(t)
			state.update(0.0)
			_rig.update_skeleton(0.0)
		await get_tree().process_frame
		RenderingServer.force_draw(false)
		var filename := "%s/%s_%s.png" % [request.out, clip, ("%.3f" % t) if clip != "setup" else "pose"]
		var err := vp.get_texture().get_image().save_png(filename)
		if err != OK:
			printerr("activity_preview: could not write ", filename, " err=", err)
			get_tree().quit(2)
			return
		records.append({"clip": clip, "time": t, "bones": _bone_world()})

	var file := FileAccess.open(String(request.out) + "/joints.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(records, "\t"))
	print("Rendered ", records.size(), " poses")


func _run_loop(request: Dictionary, vp: SubViewport, state, skeleton) -> void:
	var clip: String = request.loop.clip
	var fps := float(request.loop.fps)
	var duration := float(request.loop.duration)
	if skeleton.get_data().find_animation(clip) == null:
		printerr("Missing animation: ", clip)
		get_tree().quit(2)
		return

	skeleton.set_to_setup_pose()
	state.clear_track(0)
	state.set_animation(clip, true, 0)          # loop=true: state time wraps at clip end
	var dt := 1.0 / fps
	var n := int(round(duration * fps))
	var records := []
	for i in range(n + 1):
		var d := dt if i > 0 else 0.0             # first frame is the setup/start pose
		state.update(d)                          # advance the SAME state; wraps across 2s/4s
		_rig.update_skeleton(0.0)                # world transform only; a non-zero delta
		                                         # re-runs skeleton.update() and wipes the pose
		await get_tree().process_frame
		RenderingServer.force_draw(false)
		var filename := "%s/%s_%06.3f.png" % [request.out, clip, i * dt]
		var err := vp.get_texture().get_image().save_png(filename)
		if err != OK:
			printerr("activity_preview: could not write ", filename, " err=", err)
			get_tree().quit(2)
			return
		records.append({"time": roundf(i * dt * 1000) / 1000, "bones": _bone_world()})

	var file := FileAccess.open(String(request.out) + "/loop_joints.json", FileAccess.WRITE)
	file.store_string(JSON.stringify({"clip": clip, "fps": fps, "duration": duration,
			"frames": records}, "\t"))
	print("Loop rendered ", n + 1, " frames at ", fps, " fps")


func _bone_world() -> Dictionary:
	var out := {}
	var skeleton := _rig.get_skeleton()
	for name in ["root", "hip", "torso", "head",
			"thigh_l", "calf_l", "foot_l", "thigh_r", "calf_r", "foot_r",
			"upper_arm_l", "forearm_l", "hand_l", "upper_arm_r", "forearm_r", "hand_r",
			"chair"]:
		var bone = skeleton.find_bone(name)
		if bone != null:
			out[name] = [roundf(bone.get_world_x() * 1000) / 1000,
				roundf(bone.get_world_y() * 1000) / 1000]
	return out
