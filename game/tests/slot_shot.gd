extends Node
## Dev-only: pose one clip at one time, then render it with some slots hidden
## (or kept alone) so it is obvious which layer owns which pixels.
##
## Run: Godot --path game res://tests/slot_shot.tscn -- slack 1.2 full
##      Godot --path game res://tests/slot_shot.tscn -- slack 1.2 hide:fish
##      Godot --path game res://tests/slot_shot.tscn -- slack 1.2 solo:fish,fish_hand_l
##
## The pose is applied once and then frozen: the animation state must not run
## again or it re-applies the slot timelines and undoes the hiding.  Clearing
## the track first (the old version of this probe) resets the skeleton to its
## setup pose, which is why earlier captures showed no props at all.
##
## Every render is written to tools/_debug/slot_shot/.

const SKEL_PATH := "res://assets/pet_spine/pet.spine-json"
const ATLAS_PATH := "res://assets/pet_spine/pet.atlas"
const OUT := "I:/PetFish/tools/_debug/slot_shot"

var _vp: SubViewport
var _sprite: SpineSprite
var _base := {}


func _ready() -> void:
	DirAccess.make_dir_recursive_absolute(OUT)
	var args := OS.get_cmdline_user_args()
	var anim: String = args[0] if args.size() > 0 else "slack"
	var t: float = float(args[1]) if args.size() > 1 else 1.2
	var ops: Array = []
	if args.size() > 2:
		ops = args.slice(2)
	else:
		ops.append("full")

	_vp = SubViewport.new()
	_vp.size = Vector2i(620, 860)
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
	# the skeleton's origin is the character's centre line, so without an offset
	# half the pet renders outside the viewport
	_sprite.position = Vector2(310, 10)
	_sprite.update_mode = SpineConstant.UpdateMode_Manual
	_vp.add_child(_sprite)

	var st := _sprite.get_animation_state()
	var sk := _sprite.get_skeleton()
	sk.set_to_setup_pose()
	st.clear_track(0)
	st.set_animation(anim, false, 0)
	st.update(0.0)
	st.get_current(0).set_track_time(t)
	st.update(0.0)
	_sprite.update_skeleton(0.0)
	for s in sk.get_slots():
		var sl: SpineSlot = s
		_base[sl.get_data().get_name()] = sl.get_attachment()
	print("posed ", anim, " t=", t, " slots=", _base.size(),
		" armR2=", sk.find_bone("armR2").get_rotation(),
		" fish_att=", _base.get("fish", null))

	for op in ops:
		var keep: Array = []
		var hide: Array = []
		var parts := String(op).split(":", false, 1)
		if parts.size() > 1:
			var names := parts[1].split(",", false)
			if parts[0] == "solo":
				keep = names
			else:
				hide = names
		for slot_name in _base:
			var want: bool = true
			if keep.size() > 0 and not keep.has(slot_name):
				want = false
			if hide.has(slot_name):
				want = false
			sk.find_slot(slot_name).set_attachment(_base[slot_name] if want else null)
		await get_tree().process_frame
		await RenderingServer.frame_post_draw
		await RenderingServer.frame_post_draw
		var img := _vp.get_texture().get_image()
		img.save_png(OUT + "/" + String(op).replace(":", "_").replace(",", "_") + ".png")
		print("saved ", op, " bbox=", img.get_used_rect())
	get_tree().quit()
