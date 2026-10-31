extends Node

func _ready() -> void:
	for c in ["SpineSkeleton", "SpineSkeletonDataResource", "SpineBone"]:
		var out := []
		for m in ClassDB.class_get_method_list(c, true):
			out.append(m.name)
		out.sort()
		print("-- ", c, ": ", out)
	get_tree().quit()
