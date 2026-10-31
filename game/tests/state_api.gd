extends SceneTree


func _init() -> void:
	for cn in ["SpineAnimationState", "SpineAnimationStateTrackEntry", "SpineAnimation"]:
		print("=== ", cn)
		var ms := []
		for m in ClassDB.class_get_method_list(cn):
			ms.append(m.name)
		ms.sort()
		print("  ", ", ".join(ms))
		for s in ClassDB.class_get_signal_list(cn):
			print("  signal: ", s.name)
	quit()
