extends Node2D
## Dev-only harness: opens the reminder settings card on each tab and fires a
## sample notice, capturing the overlay so the feature UI can be inspected.
##
## Run:  Godot --path game res://tests/feature_test.tscn --resolution 380x480

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/feature_%s.png"


func _ready() -> void:
	Stage.begin(self, 120.0, "FishPet feature_test")
	var bg := ColorRect.new()
	bg.color = Color(1, 0, 1)
	bg.size = Vector2(1200, 1200)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)

	var pet = load("res://main.tscn").instantiate()
	add_child(pet)
	await get_tree().process_frame
	pet.set_process(false)

	pet._set_state("idle")
	pet._refresh_texts()
	pet._set_menu_open(true, Vector2(60, 120))
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT % "menu")
	print("saved menu")

	pet._set_menu_open(false)
	pet._entry = {}
	pet._tail.detail = ""
	pet._tail.tool_name = ""
	pet._tail.tool_count = 0
	pet._set_state("idle")
	pet._refresh_texts()
	pet._panel.visible = true
	pet._refresh_texts()
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT % "hover_panel")
	print("saved hover_panel")
	pet._panel.visible = false

	pet._open_settings()
	await get_tree().process_frame

	# Fill the lists so row clipping and scrolling are visible in the captures.
	for i in 9:
		pet._reminders.add_alarm("%02d:%02d" % [7 + i, i * 5], ["起床上班", "喝水", "站起来走走"][i % 3], "daily")
	pet._reminders.add_memo("交房租和水电费，顺便把快递取回来，别忘了带伞", "物业 302", "")
	pet._reminders.add_memo("给猫买猫粮", "", Time.get_date_string_from_system())
	pet._reminders.add_memo("周报", "周五下班前发", "")

	var tabs: TabContainer = pet._settings._tabs
	for i in tabs.get_tab_count():
		tabs.current_tab = i
		pet._settings.reload()
		await get_tree().create_timer(0.25).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(OUT % ("tab_%d" % i))
		print("saved tab ", i, " ", tabs.get_tab_title(i))

	pet._close_settings()
	await get_tree().process_frame

	# Sample notices while the pet animates them.
	var samples := [
		["water", "该喝水啦 · 还差 750 ml", 0.35, 1.2],
		["sit", "坐了一 小时啦，起来伸个懒腰", 0.6, 1.2],
		["alarm", "闹钟 09:30 · 上班", 0.18, 0.2],
	]
	for sample in samples:
		pet._on_notice(sample[0], sample[1])
		await get_tree().create_timer(sample[2]).timeout
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(OUT % ("notice_" + sample[0]))
		print("saved notice ", sample[0])

	pet._reminders.log_water(250)
	await get_tree().create_timer(0.9).timeout
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT % "water_logged")
	print("saved water_logged, today=", pet._reminders.today_ml())

	pet._notice_timer = 0.0
	pet._notice_anim_left = 0.0
	pet._set_state("slack")
	pet._refresh_texts()
	await get_tree().create_timer(0.8).timeout
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT % "slack")
	print("saved slack")

	# Typing smoke test: focus the memo title field and push a key through the
	# normal GUI pipeline.
	pet._set_state("idle")
	pet._refresh_texts()
	pet._open_settings()
	tabs.current_tab = 3
	pet._settings.reload()
	await get_tree().process_frame
	var edit: LineEdit = pet._settings._memo_title_edit
	edit.text = ""
	edit.grab_focus()
	var key := InputEventKey.new()
	key.pressed = true
	key.keycode = KEY_A
	key.unicode = 97
	Input.parse_input_event(key)
	await get_tree().process_frame
	var release := InputEventKey.new()
	release.pressed = false
	release.keycode = KEY_A
	release.unicode = 97
	Input.parse_input_event(release)
	await get_tree().process_frame
	print("typed text=", edit.text, " focus=", get_viewport().gui_get_focus_owner())

	# Mouse smoke test: click the 250 ml cup through the GUI input path.
	tabs.current_tab = 0
	await get_tree().process_frame
	var cup := _find_button(pet._settings, "一杯 250")
	if cup != null:
		var before: int = int(pet._reminders.today_ml())
		var at: Vector2 = cup.get_global_rect().get_center()
		var vp := get_viewport()
		var motion := InputEventMouseMotion.new()
		motion.position = at
		motion.global_position = at
		vp.push_input(motion)
		await get_tree().process_frame
		print("hovered at cup: ", vp.gui_get_hovered_control())
		var down := InputEventMouseButton.new()
		down.button_index = MOUSE_BUTTON_LEFT
		down.pressed = true
		down.button_mask = MOUSE_BUTTON_MASK_LEFT
		down.position = at
		down.global_position = at
		vp.push_input(down)
		await get_tree().process_frame
		var up := InputEventMouseButton.new()
		up.button_index = MOUSE_BUTTON_LEFT
		up.pressed = false
		up.button_mask = 0
		up.position = at
		up.global_position = at
		vp.push_input(up)
		await get_tree().create_timer(0.3).timeout
		print("mouse click 250: ", before, " -> ", pet._reminders.today_ml())
	else:
		print("mouse click: cup button not found")

	# The engine always writes the real profile; delete data/pet_data.json after
	# a test run if a clean slate is wanted.
	print("data file: ", pet._reminders.data_path)
	Stage.ok("feature_test finished")


func _find_button(root: Node, text: String) -> Button:
	for child in root.get_children():
		if child is Button and child.text == text:
			return child
		var found := _find_button(child, text)
		if found != null:
			return found
	return null
