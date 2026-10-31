extends Node2D
## One-frame orientation check.  Run with an optional "flip" argument:
##   Godot --path game res://tests/orient_test.tscn -- flip


func _ready() -> void:
	var flip := "flip" in OS.get_cmdline_user_args()
	var bg := ColorRect.new()
	bg.color = Color(0.12, 0.13, 0.16)
	bg.size = Vector2(2000, 2000)
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
	sprite.scale = Vector2(0.5, -0.5) if flip else Vector2(0.5, 0.5)
	sprite.position = Vector2(200, 820)
	sprite.get_animation_state().set_animation("idle", true, 0.0)

	var b = sprite.get_skeleton().find_bone("head")
	print("flip=", flip, " head world y=", b.get_world_y(), " bounds=", sprite.get_skeleton().get_bounds())
	await get_tree().create_timer(0.6).timeout
	await RenderingServer.frame_post_draw
	var img := get_viewport().get_texture().get_image()
	var name := "orient_flip.png" if flip else "orient_default.png"
	img.save_png("I:/PetFish/tools/_debug/" + name)
	print("saved ", name)
	get_tree().quit()
