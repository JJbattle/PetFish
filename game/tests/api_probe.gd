extends Node

func _ready() -> void:
	for cls in ["SpineSkeletonDataResource", "SpineAnimationState", "SpineSprite"]:
		for m in ClassDB.class_get_method_list(cls, true):
			if m["name"] in ["set_default_mix", "set_animation_mixes", "set_animation", "add_animation"]:
				print(cls, ".", m["name"], " args=", m["args"], " return=", m["return"])
	get_tree().quit()
