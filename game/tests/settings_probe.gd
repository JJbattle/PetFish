extends Node
## Dev-only: dump the settings card's control sizes to find collapsed labels,
## and capture every tab.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/settings_tab_%d.png"

func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet settings_probe")
	var pet = load("res://main.tscn").instantiate()
	add_child(pet)
	await get_tree().process_frame
	pet._open_settings()
	await get_tree().process_frame
	await get_tree().process_frame
	var settings: Control = pet._settings
	_walk(settings, 0)
	for tab in 4:
		pet._settings._tabs.current_tab = tab
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		get_viewport().get_texture().get_image().save_png(OUT % tab)
		print("saved tab ", tab)
	Stage.ok("settings_probe finished")


func _walk(node: Node, depth: int) -> void:
	if node is Control:
		var c := node as Control
		var label := ""
		if c is Label or c is Button or c is CheckBox:
			label = c.text
		if label != "" and c.size.x <= 2.0:
			print("COLLAPSED %s '%s' min=%s" % [c.get_class(), label, c.get_combined_minimum_size()])
	for child in node.get_children():
		_walk(child, depth + 1)
