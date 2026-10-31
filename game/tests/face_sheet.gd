extends Node
## Dev-only: face acceptance sheet.  Every eye / mouth attachment is rendered
## once at 4x (to judge the art) and once at the real overlay size (to judge
## whether it still reads), in the real skeleton rather than as loose layers.
##
## Run: Godot --path game res://tests/face_sheet.tscn --rendering-driver opengl3

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/face_sheet"

const EYES := ["eyes_open", "eyes_left", "eyes_right", "eyes_up", "eyes_down",
	"eyes_half", "eyes_closed", "eyes_happy"]
const MOUTHS := ["mouth_default", "mouth_sip", "mouth_smile"]


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()

	# 4x: the face fills the viewport.  The face centre is source (473, 462),
	# i.e. spine (3, -330), and spine y is rendered downwards.
	var zoom: Array = await _make_vp(
		data, Vector2i(1120, 420), 4.0, Vector2(548.0, -1110.0))
	# 0.415 x 820 px rig = the ~340 px character of the real 760x480 overlay
	var real: Array = await _make_vp(
		data, Vector2i(340, 380), 0.415, Vector2(159.0, 10.0))

	for e in EYES:
		await _shot(zoom, e, "mouth_default", "zoom_" + e)
		await _shot(real, e, "mouth_default", "actual_" + e)
	for m in MOUTHS:
		await _shot(zoom, "eyes_open", m, "zoom_" + m)
		await _shot(real, "eyes_open", m, "actual_" + m)
	get_tree().quit()


func _make_vp(data: SpineSkeletonDataResource, size: Vector2i, scale_f: float,
		pos: Vector2) -> Array:
	var vp := SubViewport.new()
	vp.size = size
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(vp)
	var sprite := SpineSprite.new()
	sprite.skeleton_data_res = data
	sprite.update_mode = SpineConstant.UpdateMode_Manual
	sprite.scale = Vector2(scale_f, scale_f)
	sprite.position = pos
	vp.add_child(sprite)
	await get_tree().process_frame
	return [vp, sprite]


func _shot(pair: Array, eyes: String, mouth: String, label: String) -> void:
	var vp: SubViewport = pair[0]
	var sprite: SpineSprite = pair[1]
	var sk := sprite.get_skeleton()
	sk.set_to_setup_pose()
	sk.set_attachment("eyes", eyes)
	sk.set_attachment("mouth", mouth)
	sprite.update_skeleton(0.0)
	await get_tree().process_frame
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	var img := vp.get_texture().get_image()
	img.save_png(OUT + "/" + label + ".png")
	print("saved ", label, " bbox=", img.get_used_rect())
