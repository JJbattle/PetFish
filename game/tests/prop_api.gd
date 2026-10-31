extends Node
func _ready() -> void:
	for cls in ["SpineSkeleton", "SpineSlot"]:
		for m in ClassDB.class_get_method_list(cls, true):
			if m["name"] in ["set_attachment", "get_attachment_by_slot_name", "get_attachment"]:
				print(cls, ".", m["name"], " args=", m["args"], " ret=", m["return"])
	get_tree().quit()
