extends SceneTree


func _init() -> void:
	for cn in ["SpineBone", "SpineBoneData"]:
		print("=== ", cn, " methods ===")
		var ms := []
		for m in ClassDB.class_get_method_list(cn):
			ms.append(m.name)
		ms.sort()
		print("  ", ", ".join(ms))
		var ps := []
		for p in ClassDB.class_get_property_list(cn):
			ps.append(p.name)
		print("  props: ", ", ".join(ps))
	quit()
