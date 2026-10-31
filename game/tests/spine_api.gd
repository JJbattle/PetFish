extends SceneTree


func _init() -> void:
	for cn in ["SpineSprite", "SpineSkeleton"]:
		if not ClassDB.class_exists(cn):
			print(cn, " missing")
			continue
		print("=== ", cn, " props ===")
		for p in ClassDB.class_get_property_list(cn):
			print("  ", p.name, " : ", p.type)
		print("=== ", cn, " methods ===")
		var ms := []
		for m in ClassDB.class_get_method_list(cn):
			ms.append(m.name)
		ms.sort()
		print("  ", ", ".join(ms))
	quit()
