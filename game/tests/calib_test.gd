extends Node2D
## Setup-pose calibration: renders the rig at a known node transform so the
## world -> screen mapping can be measured from the captured PNG.

const OUT := "I:/PetFish/tools/_debug/calib_setup.png"


func _ready() -> void:
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
	print("loaded=", data.is_skeleton_data_loaded())

	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	add_child(sprite)
	sprite.scale = Vector2(0.4, 0.4)
	sprite.position = Vector2(400, 100)

	var sk := sprite.get_skeleton()
	sk.set_to_setup_pose()
	sprite.update_skeleton(0.0)
	for n in ["root", "hip", "head", "hairL3", "tailFin"]:
		var b = sk.find_bone(n)
		print(n, " local=", b.get_x(), ",", b.get_y(),
				" world=", b.get_world_x(), ",", b.get_world_y(),
				" screen=", sprite.get_global_bone_transform(n).origin)
	print("bounds=", sk.get_bounds())

	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT)
	print("saved ", OUT)
	get_tree().quit()
