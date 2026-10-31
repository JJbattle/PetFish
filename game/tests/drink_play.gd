extends Node
## Dev-only: play the 250 ml two-handed drink exactly as pet.gd's chain does
## (drink_in -> drink_sip x2 -> drink_out, 0.12 s cross-fades) and dump frames.
##
## Run: Godot --path game res://tests/drink_play.tscn --resolution 600x840

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/drink250_anim"

const FPS := 25.0
const DT := 1.0 / FPS
# spine-godot's set_animation(name, loop, track_id) has no mix parameter; the
# third argument is the track, so pet.gd's "0.12" is a hard cut too.  Match it.
const TRACK := 0
const MAX_SECS := 5.0

var _vp: SubViewport
var _sprite: SpineSprite
var _st: SpineAnimationState
var _chain: Array = []
var _clip := ""


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	_vp = SubViewport.new()
	_vp.size = Vector2i(600, 840)
	_vp.transparent_bg = true
	_vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	add_child(_vp)

	var sf: SpineSkeletonFileResource = load(SKEL_PATH)
	var atlas: SpineAtlasResource = load(ATLAS_PATH)
	var data := SpineSkeletonDataResource.new()
	data.skeleton_file_res = sf
	data.atlas_res = atlas
	data.update_skeleton_data()

	_sprite = SpineSprite.new()
	_sprite.skeleton_data_res = data
	# Manual mode: SpineSprite otherwise advances the state in
	# NOTIFICATION_INTERNAL_PROCESS with the real frame delta, which races
	# ahead of the fixed step below (set_process(false) does not stop it).
	_sprite.update_mode = SpineConstant.UpdateMode_Manual
	_vp.add_child(_sprite)

	var win := Vector2(600, 840)
	var scale_f := minf(win.x * 0.9 / 599.0, (win.y - 90.0) / 820.0)
	_sprite.scale = Vector2(scale_f, scale_f)
	_sprite.position = Vector2(win.x * 0.5 - 26.5 * scale_f, 40.0)

	_st = _sprite.get_animation_state()
	# 250 ml / 150 ml per sip -> 2 sips, same clamp as pet.gd
	_chain = ["drink_in", "drink_sip", "drink_sip", "drink_out"]
	# first clip: reset to setup, no blend
	_sprite.get_skeleton().set_to_setup_pose()
	_chain_next()

	var frame := 0
	var t := 0.0
	while t < MAX_SECS:
		_st.update(DT)
		_sprite.update_skeleton(0.0)
		_tick_chain()
		if frame >= 60 and frame <= 84:
			var sk := _sprite.get_skeleton()
			var cb := sk.find_bone("cup")
			var hl := sk.find_bone("handL")
			var hr := sk.find_bone("handR")
			print("F", frame, " t=%.2f" % t, " ", _clip,
				" cupY=%.1f" % cb.get_world_y(),
				" handL=(%.1f,%.1f)" % [hl.get_world_x(), hl.get_world_y()],
				" handR=(%.1f,%.1f)" % [hr.get_world_x(), hr.get_world_y()])
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		_vp.get_texture().get_image().save_png(OUT + "/frame_%03d.png" % frame)
		frame += 1
		t += DT
		if _clip == "" and _chain.is_empty():
			break
	print("frames=", frame, " secs=", t)
	get_tree().quit()


func _chain_next() -> void:
	if _chain.is_empty():
		_clip = ""
		return
	_clip = str(_chain.pop_front())
	_st.set_animation(_clip, false, TRACK)


func _tick_chain() -> void:
	if _clip == "":
		return
	var entry := _st.get_current(0)
	if entry != null and entry.is_complete():
		print("advance from ", _clip, " at t=", entry.get_track_time(), "/", entry.get_animation().get_duration())
		_chain_next()
