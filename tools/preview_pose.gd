extends Node

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
	var vp := SubViewport.new()
	vp.size = Vector2i(1024, 1024)
	vp.transparent_bg = true
	vp.disable_3d = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	var rig := SpineSprite.new()
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = load("res://assets/pet.spine-json")
	data.atlas_res = load("res://assets/pet.atlas")
	data.update_skeleton_data()
	rig.skeleton_data_res = data
	rig.update_mode = 2
	rig.position = Vector2(470, 132)
	vp.add_child(rig)
	await get_tree().process_frame
	var state = rig.get_animation_state()
	var records := []
	for spec in String(request.poses).split(",", false):
		var parts := spec.split(":")
		var clip := parts[0]
		var t := float(parts[1]) if parts.size() > 1 else 0.0
		if rig.get_skeleton().get_data().find_animation(clip) == null:
			printerr("Missing animation: ", clip)
			get_tree().quit(2)
			return
		rig.get_skeleton().set_to_setup_pose()
		state.clear_track(0)
		state.set_animation(clip, false, 0)
		state.update(0.0)
		state.get_current(0).set_track_time(t)
		state.update(0.0)
		rig.update_skeleton(0.0)
		await get_tree().process_frame
		RenderingServer.force_draw(false)
		var filename := "%s/%s_%.3f.png" % [request.out, clip, t]
		var error := vp.get_texture().get_image().save_png(filename)
		if error != OK:
			get_tree().quit(2)
			return
		var joints := {}
		for name in ["head", "cup", "gripL", "gripR", "s_handL", "s_handR", "s_grip_l", "s_grip_r"]:
			var bone = rig.get_skeleton().find_bone(name)
			if bone != null:
				joints[name] = [470 + bone.get_world_x(), 132 + bone.get_world_y()]
		records.append({"clip": clip, "time": t, "joints": joints})
	var file := FileAccess.open(String(request.out) + "/joints.json", FileAccess.WRITE)
	file.store_string(JSON.stringify(records, "\t"))
	print("Rendered ", records.size(), " poses; exiting isolated preview")
	get_tree().quit()
