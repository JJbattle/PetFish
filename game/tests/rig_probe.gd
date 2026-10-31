extends Node
## Dev-only: isolate each slot to find misplaced layers.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/probe"

const SLOTS := ["hair_l", "hair_r", "tail", "body", "skirt",
	"arm_up_l", "arm_up_r", "arm_fore_l", "hand_l", "arm_fore_r",
	"head", "eyes", "mouth", "cup", "hand_r"]

var sprite: SpineSprite
var vp: SubViewport
var base := {}


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	vp = SubViewport.new()
	vp.size = Vector2i(1000, 1200)
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()
	print("loaded=", data.is_skeleton_data_loaded(),
		" wh=", data.get_width(), "x", data.get_height(),
		" xy=", data.get_x(), ",", data.get_y(),
		" ref=", data.get_reference_scale())
	sprite = SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.position = Vector2(500, 100)
	sprite.scale = Vector2(1, 1)
	vp.add_child(sprite)

	await get_tree().process_frame
	await get_tree().process_frame
	var sk := sprite.get_skeleton()
	var bi := 0
	for b in sk.get_bones():
		print("bone[%d] local=" % bi, b.get_x(), ",", b.get_y(),
			" world=", b.get_world_x(), ",", b.get_world_y(),
			" gxform=", b.get_global_transform())
		bi += 1

	for s in SLOTS:
		base[s] = sk.find_slot(s).get_attachment()
		print("att ", s, " name=", base[s].get_attachment_name() if base[s] else "<null>")

	for s in SLOTS:
		_show_only(s)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img: Image = vp.get_texture().get_image()
		var bb := img.get_used_rect()
		print("SLOT ", s, " bbox=", bb, "  rel y=", bb.position.y - 100)
		img.save_png(OUT + "/only_" + s + ".png")

	_show_only("")
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	vp.get_texture().get_image().save_png(OUT + "/all.png")
	print("done")
	get_tree().quit()


func _show_only(keep: String) -> void:
	var sk := sprite.get_skeleton()
	for s in SLOTS:
		var slot := sk.find_slot(s)
		if slot == null:
			print("missing slot ", s)
			continue
		if s == keep:
			slot.set_attachment(base[s])
		else:
			slot.set_attachment(null)
