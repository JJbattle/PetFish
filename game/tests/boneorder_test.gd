extends Node2D


func _ready() -> void:
	var sf: SpineSkeletonFileResource = load("res://assets/pet_spine/pet.spine-json")
	var atlas: SpineAtlasResource = load("res://assets/pet_spine/pet.atlas")
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()

	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	add_child(sprite)
	var sk := sprite.get_skeleton()
	var bones = sk.get_bones()
	print("count=", bones.size())
	for i in range(bones.size()):
		var b = bones[i]
		var d = b.get_data()
		print(i, " ", d.get_bone_name(), " idx=", d.get_index())
	get_tree().quit()
