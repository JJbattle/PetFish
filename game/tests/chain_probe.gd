extends Node
## Dev-only: log the chain clip and a few bone values over time, to check sip
## counts and that a clip hand-off does not snap the pose.

const Stage = preload("res://tests/test_stage.gd")
var pet: Control
var t := 0.0
var last := ""


func _ready() -> void:
	Stage.begin(self, 60.0, "FishPet chain_probe")
	var scene: PackedScene = load("res://main.tscn")
	pet = scene.instantiate()
	add_child(pet)
	await get_tree().process_frame
	await get_tree().process_frame
	pet.start_chain(["drink_in", "drink_sip", "drink_sip", "drink_out"])
	print("start chain")


func _process(delta: float) -> void:
	t += delta
	var sk = pet._rig.get_skeleton()
	var clip: String = pet._chain_clip
	print("%6.3f clip=%-10s anim=%-10s root=(%.2f,%.2f) head=%.2f handR=(%.2f,%.2f)" % [
		t, clip, pet._anim,
		sk.find_bone("root").get_x(), sk.find_bone("root").get_y(),
		sk.find_bone("head").get_rotation(),
		sk.find_bone("handR").get_world_x(), sk.find_bone("handR").get_world_y()])
	if t > 4.4:
		set_process(false)
		Stage.ok("chain_probe finished")
