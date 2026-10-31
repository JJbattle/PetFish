extends Node2D
## Dev-only: render the rig at a known node transform to calibrate local coords.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/calib2.png"


func _ready() -> void:
	var bg := ColorRect.new()
	bg.color = Color(0.08, 0.08, 0.10)
	bg.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	add_child(bg)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	print("loaded=", data.is_skeleton_data_loaded())
	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.position = Vector2(200, 80)
	sprite.scale = Vector2(1, 1)
	add_child(sprite)

	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	get_viewport().get_texture().get_image().save_png(OUT)
	var img: Image = get_viewport().get_texture().get_image()
	var used := img.get_region(Rect2i(0, 0, img.get_width(), img.get_height()))
	print("viewport ", img.get_width(), "x", img.get_height(), " saved ", OUT)
	get_tree().quit()
