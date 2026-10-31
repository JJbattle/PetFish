extends Node
## Dev-only: capture each animation at the real 380x480 window size.

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/app_states"
const CLIPS := [
	["idle", 0.0], ["idle", 1.1],
	["working", 0.4], ["working", 1.2],
	["slack", 1.2], ["slack", 3.0],
	["needs_input", 0.9], ["needs_input", 1.7],
	["done", 0.4], ["cheer", 0.6],
	["stretch", 0.6], ["stretch", 1.6],
	["water_remind", 1.4],
	["present", 0.8], ["present2", 0.9],
]

var pet: Control


func _ready() -> void:
	Stage.begin(self, 90.0, "FishPet app_states")
	DirAccess.make_dir_recursive_absolute(OUT)
	var scene: PackedScene = load("res://main.tscn")
	pet = scene.instantiate()
	add_child(pet)
	await get_tree().process_frame
	await get_tree().process_frame
	pet.set_process(false)  # freeze the state machine; drive the rig by hand
	var rig: SpineSprite = pet._rig
	var st := rig.get_animation_state()
	for item in CLIPS:
		var anim: String = item[0]
		var t: float = item[1]
		rig.get_skeleton().set_to_setup_pose()
		st.clear_track(0)
		st.set_animation(anim, false, 0.0)
		st.update(0.0)
		st.get_current(0).set_track_time(t)
		st.update(0.0)
		rig.update_skeleton(0.0)
		var sk := rig.get_skeleton()
		print("POSE ", anim, " ", t, " armR2=", sk.find_bone("armR2").get_rotation(),
			" handR=", sk.find_bone("handR").get_world_x(), ",", sk.find_bone("handR").get_world_y())
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := get_viewport().get_texture().get_image()
		var name := "%s_%.1f" % [anim, t]
		img.save_png(OUT + "/" + name + ".png")
		print("saved ", name, " bbox=", img.get_used_rect())
	Stage.ok("app_states captured %d poses" % CLIPS.size())
