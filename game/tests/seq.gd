extends Node
## Dev-only: render a schedule of (label, animation, time) key poses.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"

const SCHEDULE := [
	["idle_0", "idle", 0.0],
	["idle_1", "idle", 1.1],
	["idle_blink", "idle", 2.25],
	["working_0", "working", 0.0],
	["working_1", "working", 1.2],
	["slack_0", "slack", 0.0],
	["slack_1", "slack", 3.0],
	["needs_0", "needs_input", 0.5],
	["needs_1", "needs_input", 1.5],
	["done_0", "done", 0.5],
	["cheer_0", "cheer", 0.8],
	["stretch_0", "stretch", 0.6],
	["stretch_1", "stretch", 1.7],
	["wrem_0", "water_remind", 0.5],
	["wrem_1", "water_remind", 1.6],
	["din_0", "drink_in", 0.0],
	["din_1", "drink_in", 0.3],
	["din_2", "drink_in", 0.55],
	["din_3", "drink_in", 0.85],
	["sip_0", "drink_sip", 0.0],
	["sip_1", "drink_sip", 0.3],
	["sip_2", "drink_sip", 0.55],
	["sip_3", "drink_sip", 0.8],
	["sip_4", "drink_sip", 1.0],
	["dout_0", "drink_out", 0.0],
	["dout_1", "drink_out", 0.4],
	["dout_2", "drink_out", 0.62],
	["dout_3", "drink_out", 0.85],
]

var vp: SubViewport
var sprite: SpineSprite


func _ready() -> void:
	var out := "I:/PetFish/tools/_debug/seq"
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		out = args[0]
	DirAccess.make_dir_recursive_absolute(out)

	vp = SubViewport.new()
	vp.size = Vector2i(600, 840)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	sprite = SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.position = Vector2(300, 10)
	vp.add_child(sprite)

	var st := sprite.get_animation_state()
	for entry in SCHEDULE:
		var label: String = entry[0]
		var anim: String = entry[1]
		var t: float = entry[2]
		# clips only override the channels they key; clear leftovers so a key
		# pose does not inherit the arm of a previous one.
		var sk := sprite.get_skeleton()
		if sk != null and not (label.begins_with("sip_") or label.begins_with("dout_")):
			sk.set_to_setup_pose()
		st.clear_track(0)
		st.set_animation(anim, false, 0.0)
		st.update(0.0)
		var cur := st.get_current(0)
		if cur != null:
			cur.set_track_time(t)
		st.update(0.0)
		sprite.update_skeleton(0.0)
		sk = sprite.get_skeleton()
		var b = sk.find_bone("armR2")
		var h = sk.find_bone("handR")
		var c = sk.find_bone("cup")
		var att := func(slot_name: String) -> String:
			var slot := sk.find_slot(slot_name)
			var a := slot.get_attachment()
			return "<none>" if a == null else a.get_attachment_name()
		print("STATE ", label, " armR2 rot=", b.get_rotation(), " world=", b.get_world_x(), ",", b.get_world_y(),
			" hand=", h.get_world_x(), ",", h.get_world_y(),
			" cup world=", c.get_world_x(), ",", c.get_world_y(),
			" cup=", att.call("cup"), " cupA=", sk.find_slot("cup").get_color().a,
			" eyes=", att.call("eyes"), " mouth=", att.call("mouth"),
			" hand_r=", att.call("hand_r"))
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		vp.get_texture().get_image().save_png(out + "/" + label + ".png")
		print("saved ", label, " bbox=", vp.get_texture().get_image().get_used_rect())
	get_tree().quit()
