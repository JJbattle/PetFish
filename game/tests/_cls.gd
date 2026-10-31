extends SceneTree
func _init():
	for m in ClassDB.class_get_method_list("SpineSkeleton", true):
		print("M ", m.name)
	quit()
