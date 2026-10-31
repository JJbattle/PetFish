extends Node2D

const OUT := "I:/PetFish/tools/_debug/"


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = Color(1, 0, 1)
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
	sprite.scale = Vector2(0.5, 0.5)
	sprite.position = Vector2(300, 40)

	var sk := sprite.get_skeleton()
	await get_tree().process_frame

	print("slots=", sk.get_slots().size())
	for n in ["hip", "tail1", "tail2", "tailFin", "head"]:
		var t: Transform2D = sprite.get_global_bone_transform(n)
		print("bone ", n, " screen origin=", t.origin, " x=", t.x, " y=", t.y)


	sk.set_attachment("body", "")
	await _shot("parts_tailonly")
	sk.set_attachment("tail", "")
	sk.set_attachment("body", "body")
	await _shot("parts_bodyonly")
	get_tree().quit()


func _shot(name: String) -> void:
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT + name + ".png")
	print("saved ", name)
