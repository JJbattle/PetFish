extends Node
## Isolated renderer for the standalone rest rig (see tools/rest_preview.py).
## Loads rest.spine-json + rest.atlas, poses requested clips at requested times,
## saves one PNG per pose, and dumps the world positions of the six piece bones
## so the skeleton's coordinate convention can be verified against assembly.json.

var _rig: SpineSprite


func _ready() -> void:
	get_window().always_on_top = false
	get_window().unfocusable = true
	get_window().mode = Window.MODE_MINIMIZED
	Engine.max_fps = 30
	var timer := Timer.new()
	timer.one_shot = true
	timer.wait_time = 45.0
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

	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = load("res://assets/rest.spine-json")
	data.atlas_res = load("res://assets/rest.atlas")
	data.update_skeleton_data()
	if not data.is_skeleton_data_loaded():
		printerr("rest_preview: skeleton data failed to load")
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
	var records := []
	for spec in String(request.poses).split(",", false):
		var parts := spec.split(":")
		var clip := parts[0]
		var t := float(parts[1]) if parts.size() > 1 else 0.0
		if _rig.get_skeleton().get_data().find_animation(clip) == null:
			printerr("Missing animation: ", clip)
			get_tree().quit(2)
			return
		_rig.get_skeleton().set_to_setup_pose()
		state.clear_track(0)
		state.set_animation(clip, false, 0)
		state.update(0.0)
		state.get_current(0).set_track_time(t)
		state.update(0.0)
		_rig.update_skeleton(0.0)
		await get_tree().process_frame
		RenderingServer.force_draw(false)
		var filename := "%s/%s_%.3f.png" % [request.out, clip, t]
		var err := vp.get_texture().get_image().save_png(filename)
		if err != OK:
			printerr("rest_preview: could not write ", filename, " err=", err)
			get_tree().quit(2)
			return
		records.append({"clip": clip, "time": t, "bones": _bone_world()})

	var file := FileAccess.open(String(request.out) + "/joints.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(records, "\t"))
	print("Rendered ", records.size(), " poses; bones=", JSON.stringify(_bone_world()))
	get_tree().quit()


func _bone_world() -> Dictionary:
	var out := {}
	var skeleton := _rig.get_skeleton()
	for name in ["root", "rest_body", "pillow", "head_sleep", "arm_far", "whale", "arm_near"]:
		var bone = skeleton.find_bone(name)
		if bone != null:
			out[name] = [roundf(bone.get_world_x() * 1000) / 1000,
				roundf(bone.get_world_y() * 1000) / 1000]
	return out
