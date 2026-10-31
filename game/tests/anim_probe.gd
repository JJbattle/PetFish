extends Node2D


func _ready() -> void:
	var sf: SpineSkeletonFileResource = load("res://assets/pet_spine/probe.spine-json")
	var atlas: SpineAtlasResource = load("res://assets/pet_spine/pet.atlas")
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()

	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	add_child(sprite)

	var sk := sprite.get_skeleton()
	var head := sk.find_bone("head")
	var state := sprite.get_animation_state()
	state.set_animation("t_head", false, 0.0)

	for i in range(6):
		await get_tree().create_timer(0.3).timeout
		print("i=", i, " head_rot=", head.get_rotation(), " world=", head.get_world_x(), ",", head.get_world_y())
	get_tree().quit()
