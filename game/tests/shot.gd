extends Node
## Dev-only: render the rig in a fixed-size viewport for inspection.
## Usage: -- rig_shot.png [anim] [time] [scale]

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"

var vp: SubViewport


func _ready() -> void:
	var args := OS.get_cmdline_user_args()
	var out := "I:/PetFish/tools/_debug/rig_shot.png"
	var anim := ""
	var at := 0.0
	var sc := 1.0
	if args.size() > 0:
		out = args[0]
	if args.size() > 1:
		anim = args[1]
	if args.size() > 2:
		at = float(args[2])
	if args.size() > 3:
		sc = float(args[3])

	vp = SubViewport.new()
	vp.size = Vector2i(900, 1000)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)

	var skel_path := SKEL_PATH
	var atlas_path := ATLAS_PATH
	if args.size() > 4:
		skel_path = args[4] + "/pet.spine-json"
		atlas_path = args[4] + "/pet.atlas"
	var sf: SpineSkeletonFileResource = load(skel_path)
	var atlas: SpineAtlasResource = load(atlas_path)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.scale = Vector2(sc, sc)
	sprite.position = Vector2(450, 100)
	vp.add_child(sprite)

	if anim != "":
		var st := sprite.get_animation_state()
		st.set_animation(anim, true, 0.0)
		st.update(at)
		sprite.update_skeleton(at)
	else:
		sprite.update_skeleton(0.0)
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img: Image = vp.get_texture().get_image()
	img.save_png(out)
	print("saved ", out, " anim=", anim, " t=", at, " scale=", sc,
		" bbox=", img.get_used_rect(), " sprite_pos=")
	get_tree().quit()
