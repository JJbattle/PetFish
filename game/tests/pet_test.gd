extends Node2D
## End-to-end check of the real pet scene: forces each session state and
## captures the overlay so the rig, placement and UI can be inspected.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/pet_%s.png"
const STATES := ["idle", "working", "needs_input", "done", "ended"]


func _ready() -> void:
	Stage.begin(self, 90.0, "FishPet pet_test")
	var vp := Stage.make_stage(self, Vector2i(760, 480))
	var bg := ColorRect.new()
	bg.color = Color(1, 0, 1)
	bg.size = Vector2(760, 480)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	vp.add_child(bg)
	vp.move_child(bg, 0)
	await Stage.settled()
	var pet = vp.get_child(1)
	pet.set_process(false)

	for s in STATES:
		pet._set_state(s)
		await get_tree().create_timer(0.9).timeout
		Stage.save_png(await Stage.grab(vp), OUT % s)
		print("saved ", s)

	# Cards on the character's right: the hover panel, the right-click menu and
	# the settings card, each behind the "present" pose.
	pet._set_state("working")
	pet._panel.visible = true
	pet._play("present")
	await get_tree().create_timer(0.7).timeout
	Stage.save_png(await Stage.grab(vp), OUT % "panel")
	print("saved panel")

	pet._panel.visible = false
	pet._set_menu_open(true)
	pet._play("present")
	await get_tree().create_timer(0.7).timeout
	Stage.save_png(await Stage.grab(vp), OUT % "menu")
	print("saved menu")

	pet._set_menu_open(false)
	pet._open_settings()
	pet._play("present")
	await get_tree().create_timer(0.7).timeout
	Stage.save_png(await Stage.grab(vp), OUT % "settings")
	print("saved settings")
	Stage.ok("pet_test captured %d states + 3 cards" % STATES.size())
