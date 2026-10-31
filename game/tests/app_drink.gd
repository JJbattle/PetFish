extends Node
## Dev-only: boot the real pet scene, run a 250 ml drink chain, and capture the
## live window (transparent) frame by frame.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/app"
# the 250 ml chain: two sips, each draining the bottle a step further
const CLIPS := ["drink_in", "drink_sip", "drink_sip2", "drink_out"]

var pet: Control
var frames := 0


func _ready() -> void:
	Stage.begin(self, 95.0, "FishPet app_drink")
	DirAccess.make_dir_recursive_absolute(OUT)
	var scene: PackedScene = load("res://main.tscn")
	pet = scene.instantiate()
	add_child(pet)
	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	_capture("rest")

	pet.start_chain(CLIPS)
	print("chain=", CLIPS, " dur=", 0.85 + 2.0 + 0.85)

	var t := 0.0
	var step := 1.0 / 24.0
	var next := 0.0
	while t < 6.2:
		await get_tree().process_frame
		t += get_process_delta_time()
		if t >= next:
			next += step
			_capture("f%03d" % frames)
			frames += 1
	print("captured ", frames, " frames, chain_clip=", pet._chain_clip, " left=", pet._chain.size())
	Stage.ok("app_drink finished")


func _capture(name: String) -> void:
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	img.save_png(OUT + "/" + name + ".png")
