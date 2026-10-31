extends Node2D
## Weight-placement probe: rotates a named bone hard and captures the result.

const OUT := "I:/PetFish/tools/_debug/probe_%s.png"


func _ready() -> void:
	var bone_name: String = OS.get_cmdline_user_args()[0] if OS.get_cmdline_user_args().size() > 0 else "tailFin"
	var angle: float = float(OS.get_cmdline_user_args()[1]) if OS.get_cmdline_user_args().size() > 1 else 45.0

	var bg := ColorRect.new()
	bg.color = Color(1, 0, 1)
	bg.size = Vector2(2000, 2000)
	bg.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(bg)

	var sf: SpineSkeletonFileResource = load("res://assets/pet_spine/pet.spine-json")
	var atlas: SpineAtlasResource = load("res://assets/pet_spine/pet.atlas")
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()

	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	add_child(sprite)
	sprite.scale = Vector2(0.6, 0.6)
	sprite.position = Vector2(400, 180)
	sprite.set_process(false)

	var sk := sprite.get_skeleton()
	sk.set_to_setup_pose()
	sk.find_bone(bone_name).set_rotation(angle)
	sprite.update_skeleton(0.0)

	await get_tree().process_frame
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT % bone_name)
	print("saved ", bone_name, " ", angle, " scale=", sprite.scale)
	get_tree().quit()
