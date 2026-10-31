extends SceneTree

func _initialize() -> void:
	for m in ClassDB.class_get_method_list("SpineBone"):
		if "rotation" in m.name or "scale" in m.name:
			print("M ", m.name, " args=", m.args)
	for p in ClassDB.class_get_property_list("SpineBone"):
		if "rotation" in p.name:
			print("P ", p.name, " type=", p.type)
	quit()
