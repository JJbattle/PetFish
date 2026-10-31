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
	sprite.position = Vector2(100, 300)
	var sk := sprite.get_skeleton()
	print("scale_y default=", sk.get_scale_y(), " x=", sk.get_scale_x())
	sk.set_to_setup_pose()
	sprite.update_skeleton(0.0)
	_report(sk, sprite)
	sk.set_scale_y(-1.0)
	sprite.update_skeleton(0.0)
	print("after set -1: scale_y=", sk.get_scale_y())
	_report(sk, sprite)
	get_tree().quit()


func _report(sk, sprite: SpineSprite) -> void:
	for n in ["root", "hip", "head", "hairL3", "tailFin"]:
		var b = sk.find_bone(n)
		print("  ", n, " local=", b.get_x(), ",", b.get_y(), " world=", b.get_world_x(), ",", b.get_world_y())
	print("  sprite pos=", sprite.position, " sk x,y=", sk.get_x(), ",", sk.get_y())
