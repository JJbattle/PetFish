extends Node
## Real production scripts + real Spine runtime, but no overlay window/data.
const Pet = preload("res://scripts/pet.gd")
const Silhouette = preload("res://scripts/silhouette.gd")
const HANDS := ["hand_l", "hand_r", "hand_l_front", "hand_r_front",
	"fish_hand_l", "fish_hand_r", "fish_hand_l_front", "fish_hand_r_front",
	"cup_hand_l", "cup_hand_r", "book_hand", "pen_hand",
	"s_arm_fore_l", "s_arm_fore_r", "drink_arms", "work_arms"]
var failures := 0
var checks := 0
var pet


func check(ok: bool, message: String) -> void:
	checks += 1
	if not ok:
		failures += 1
		if failures <= 20:
			printerr("FAIL: ", message)


func visible_hands() -> int:
	var count := 0
	for name in HANDS:
		var slot = pet._rig.get_skeleton().find_slot(name)
		if slot.get_attachment() != null and slot.get_color().a > 0.01:
			count += 2 if name in ["drink_arms", "work_arms"] else 1
	return count


func duration(value) -> float:
	var longest := 0.0
	if value is Dictionary:
		longest = float(value.get("time", 0))
		for child in value.values():
			longest = maxf(longest, duration(child))
	elif value is Array:
		for child in value:
			longest = maxf(longest, duration(child))
	return longest


func reset_playback() -> void:
	pet._chain.clear()
	pet._chain_clip = ""
	pet._queue.clear()
	pet._chain_tail = ""
	pet._active_key = ""
	pet._present_phase = ""
	pet._menu_open = false
	pet._settings_open = false
	pet._attention_clip = ""
	pet._state = "idle"
	pet._anim = ""
	pet._play("idle", true, true)


func advance(seconds: float) -> void:
	for i in range(int(seconds * 60)):
		pet._rig.update_skeleton(1.0 / 60)
		pet._animate(1.0 / 60)


func _ready() -> void:
	pet = Pet.new()
	pet.test_window = true
	add_child(pet)
	pet.set_process(false)
	pet._rig.update_mode = 2
	check(is_equal_approx(pet._pet_rect.size.y, 170), "default height is 170 px")
	check(pet._reminders.data_path.begins_with("user://preview_"), "isolated reminder profile")
	check(not pet._reminders.is_processing(), "no autonomous reminders in preview")
	check(not get_window().always_on_top, "no topmost preview")
	var document = JSON.parse_string(FileAccess.get_file_as_string("res://assets/pet_spine/pet.spine-json"))
	var state = pet._rig.get_animation_state()
	# Every clip, including attachment boundaries, evaluated by Spine itself.
	for clip in document.animations:
		var end := duration(document.animations[clip])
		state.clear_track(0)
		pet._anim = ""
		pet._play(clip, false, true)
		for i in range(int(ceil(end * 60)) + 1):
			var t := minf(float(i) / 60, end)
			state.get_current(0).set_track_time(t)
			pet._rig.update_skeleton(0.0)
			check(visible_hands() == 2, "%s %.3f: expected 2 hands, saw %d" % [clip, t, visible_hands()])
			if clip == "slack":
				var skeleton = pet._rig.get_skeleton()
				var shoulder = skeleton.find_bone("armR1")
				var elbow = skeleton.find_bone("armR2")
				var wrist = skeleton.find_bone("handR")
				var target = skeleton.find_bone("slackR")
				var a := Vector2(shoulder.get_world_x(), shoulder.get_world_y())
				var b := Vector2(elbow.get_world_x(), elbow.get_world_y())
				var c := Vector2(wrist.get_world_x(), wrist.get_world_y())
				var goal := Vector2(target.get_world_x(), target.get_world_y())
				check(c.distance_to(goal) < .15, "petting wrist reaches palm without an IK singularity")
				var margin := a.distance_to(goal) - absf(a.distance_to(b) - b.distance_to(c))
				check(margin > 20, "petting target stays clear of the fully folded elbow")
			if clip.begins_with("drink"):
				for side in ["L", "R"]:
					var wrist = pet._rig.get_skeleton().find_bone("d_hand" + side)
					var grip = pet._rig.get_skeleton().find_bone("d_grip" + side)
					var distance := Vector2(wrist.get_world_x(), wrist.get_world_y()).distance_to(Vector2(grip.get_world_x(), grip.get_world_y()))
					check(distance < 0.15, "%s %.3f: %s wrist reaches rigid cup (%.3f px)" % [clip, t, side, distance])
	# Exercise actual mix durations, without resetting between clips.
	var sequence := ["idle", "slack_in", "slack", "slack_out", "idle",
		"working_in", "working", "working_out", "present_in", "present",
		"present_out", "present2_in", "present2", "present2_out", "drink_in",
		"drink_sip", "drink_sip2", "drink_sip3", "drink_out", "hop_alarm", "idle"]
	state.clear_track(0)
	pet._anim = ""
	for clip in sequence:
		pet._play(clip, false)
		for i in range(int(ceil(duration(document.animations[clip]) * 60))):
			pet._rig.update_skeleton(1.0 / 60)
			check(visible_hands() == 2, "mixed %s frame %d: %d hands" % [clip, i, visible_hands()])
		check(state.get_current(0).get_track_time() > 0.1, "manual advance moves Spine clock")
	# The actual production polygon must cover the sampled union without an
	# invisible input-catching strip above the character.
	var shape: PackedVector2Array = Silhouette.build(pet._pet_image, pet._sil_rect, [], Pet.WIN_SIZE)
	check(not Geometry2D.is_point_in_polygon(Vector2(Pet.PET_CENTER_X, 30), shape), "blank space above pet passes through")
	var missed := 0
	for y in range(0, pet._pet_image.get_height(), 3):
		for x in range(0, pet._pet_image.get_width(), 3):
			if pet._pet_image.get_pixel(x, y).a < .5:
				continue
			var point = pet._sil_rect.position + Vector2(x, y) / 1024.0 * pet._sil_rect.size
			if not Geometry2D.is_point_in_polygon(point, shape):
				missed += 1
	check(missed == 0, "silhouette coverage: %d sampled opaque pixels outside polygon" % missed)
	for rect in [Pet.PANEL_RECT, Pet.SETTINGS_RECT, Pet.BUBBLE_RECT]:
		var panel_shape := Silhouette.build(pet._pet_image, pet._sil_rect, [rect], Pet.WIN_SIZE)
		for point in [rect.position + Vector2.ONE, rect.end - Vector2.ONE,
			Vector2(rect.position.x + 1, rect.end.y - 1), Vector2(rect.end.x - 1, rect.position.y + 1)]:
			check(Geometry2D.is_point_in_polygon(point, panel_shape), "open UI corner %s in %s stays inside draw region" % [point, rect])
	# A duplicate reminder must not interrupt an active drink or queue twice.
	pet._chain.clear()
	pet._chain_clip = ""
	pet._queue.clear()
	pet._anim = "idle"
	pet.start_chain(["drink_in", "drink_sip", "drink_out"], "drink-test")
	pet.start_chain(["hop_memo"], "memo-test")
	pet.start_chain(["hop_memo"], "memo-test")
	check(pet._chain_clip == "drink_in", "reminder cannot cut into drink")
	check(pet._queue.size() == 1, "duplicate reminders collapse")
	for amount in [100, 250, 500]:
		pet._chain.clear()
		pet._chain_clip = ""
		pet._queue.clear()
		pet._active_key = ""
		pet._anim = "idle"
		pet._on_water_logged(amount, amount, 2000)
		var expected: int = {100: 1, 250: 2, 500: 3}[amount]
		check(pet._chain_clip == "drink_in", "water logging starts with cup entry")
		check(pet._chain.size() == expected + 1, "%d ml queues %d sips plus exit" % [amount, expected])
		check(pet._chain.back() == "drink_out", "water logging always puts cup away")
	# Reminder looping and fixed presentation roles exercise production code.
	reset_playback()
	pet._on_notice("sit", "test")
	advance(12.0)
	check(pet._anim == "hop_sit" and not pet._chain_busy(), "reminder remains a loop after twelve seconds")
	pet._set_menu_open(true)
	advance(2.0)
	check(pet._anim == "present", "right-click menu uses display one")
	pet._open_settings()
	advance(2.0)
	check(pet._anim == "present2", "settings use display two")
	pet._close_settings()
	advance(2.0)
	check(pet._anim == "hop_sit", "unacknowledged reminder resumes after settings")
	pet._dismiss_notice()
	advance(2.0)
	check(pet._anim == "idle", "acknowledged reminder stops")
	pet._set_menu_open(true)
	advance(2.0)
	check(pet._anim == "present", "reopening menu does not alternate poses")
	reset_playback()
	pet._set_state("needs_input")
	advance(8.0)
	check(pet._anim == "needs_input", "waiting loops continuously")
	pet._show_panel(true)
	advance(1.0)
	check(pet._anim == "needs_input", "hover information does not interrupt waiting")
	pet._set_state("idle")
	advance(1.0)
	check(pet._anim == "idle", "resolved waiting stops waving")
	print("REGRESSION: ", checks, " checks, ", failures, " failures; ", document.animations.size(), " clips + mixed sequences")
	get_tree().quit(0 if failures == 0 else 1)
