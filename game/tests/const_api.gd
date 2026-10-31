extends SceneTree


func _init() -> void:
	for cn in ["SpineConstant", "SpineSprite"]:
		if not ClassDB.class_exists(cn):
			print("missing ", cn)
			continue
		var cs := []
		for c in ClassDB.class_get_integer_constant_list(cn):
			cs.append("%s=%d" % [c, ClassDB.class_get_integer_constant(cn, c)])
		print(cn, ": ", ", ".join(cs))
	quit()
