extends Node
## Dev-only: open each card in turn and capture the real overlay, to check the
## one-/two-handed present alternation and that nothing covers the character.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/panels"


func _ready() -> void:
	Stage.begin(self, 90.0, "FishPet panel_probe")
	DirAccess.make_dir_recursive_absolute(OUT)
	var pet: Control = load("res://main.tscn").instantiate()
	add_child(pet)
	await get_tree().process_frame
	await get_tree().process_frame

	# Hover card: entry clip, hold loop, then the exit once the card closes.
	pet._show_panel(true)
	await _hold(8)
	await _cap("1a_panel_in", pet)
	await _hold(28)
	await _cap("1b_panel_hold", pet)

	pet._show_panel(false)
	await _hold(8)
	await _cap("1c_panel_out", pet)

	pet._set_menu_open(true)
	await _hold(10)
	await _cap("2a_menu_in", pet)
	await _hold(38)
	await _cap("2b_menu_hold", pet)

	pet._set_menu_open(false)
	pet._open_settings()
	await _hold(48)
	await _cap("3_settings", pet)
	Stage.ok("panel_probe finished")


func _hold(frames: int) -> void:
	for i in frames:
		await get_tree().process_frame


func _cap(name: String, pet: Control) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(OUT + "/" + name + ".png")
	print("saved ", name, " anim=", pet._anim, " clip=", pet._present_clip,
		" phase=", pet._present_phase, " busy=", pet._chain_busy())
