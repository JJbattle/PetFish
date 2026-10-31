extends Node
## Dev-only: drive the real pet through a scripted timeline of session states,
## hover cards, reminders and a drink, sampling frames at 10 fps so the
## transitions can be reviewed as a contact sheet.
##
## Run: godot --path game --rendering-driver opengl3 res://tests/playback_test.tscn
## Out: tools/_debug/playback/<t>.png  + a log of anim/chain/queue changes

const Stage = preload("res://tests/test_stage.gd")
const OUT := "I:/PetFish/tools/_debug/playback"
const FPS := 10.0
const END := 52.0


class FakeStore extends RefCounted:
	var state := "idle"

	func best(_pinned: String) -> Dictionary:
		return {
			"session_id": "playback",
			"state": state,
			"ts": Time.get_unix_time_from_system(),
			"project": "PetFish",
			"transcript_path": "",
			"tool_count": 3,
			"tool_name": "Edit",
		}

	func effective_state(entry: Dictionary) -> String:
		return str(entry.get("state", "idle"))

	func next_session(_id: String) -> String:
		return ""


var pet: Control
var store: FakeStore
var vp: SubViewport
var t := 0.0
var next_shot := 0.0
var next_step := 0
var last_line := ""
var wait_hop_seen := false
var steps: Array = []


func _ready() -> void:
	Stage.begin(self, 120.0, "FishPet playback")
	for f in DirAccess.get_files_at(OUT):
		if f.ends_with(".png"):
			DirAccess.remove_absolute(OUT + "/" + f)
	vp = Stage.make_stage(self, Vector2i(380, 480))
	await Stage.settled()
	pet = vp.get_child(0)
	store = FakeStore.new()
	pet._store = store
	# autonomous reminders would make the timeline non-deterministic (and they
	# write to the user's reminder file); fire them by hand instead
	if pet._reminders != null and pet._reminders.notice.is_connected(pet._on_notice):
		pet._reminders.notice.disconnect(pet._on_notice)
	steps = [
		[0.6, func(): store.state = "working"],
		# hover while working: the notebook must be put away, not popped
		[3.0, func(): pet._show_panel(true)],
		[5.5, func(): pet._show_panel(false)],
		# two identical reminders 0.2 s apart: the second must be dropped
		[8.0, func(): pet._on_notice("sit", "该起来活动啦")],
		[8.2, func(): pet._on_notice("sit", "该起来活动啦")],
		# hover must not take the stage away from a running reminder
		[9.0, func(): pet._show_panel(true)],
		[10.0, func(): pet._show_panel(false)],
		[12.0, func(): pet._on_notice("water", "喝口水吧")],
		# a drink asked for mid-reminder waits for it
		[16.0, func(): pet._on_water_logged(250, 250, 2000)],
		# a reminder landing mid-sip must wait: no half sip, and the hover card
		# must not steal the stage from the drink either
		[18.8, func(): pet._on_notice("memo", "记得记账")],
		[19.3, func(): pet._show_panel(true)],
		[19.8, func(): pet._show_panel(false)],
		# hover after the drink: book out, offer, book back
		[22.5, func(): pet._show_panel(true)],
		[25.0, func(): pet._show_panel(false)],
		# the waiting state hops once, then stays quiet; the three reminder
		# kinds must look different from each other
		[28.0, func(): store.state = "needs_input"],
		[34.0, func(): pet._on_notice("memo", "记得记账")],
		[37.0, func(): pet._on_notice("alarm", "闹钟")],
		# a long-parked prompt gets one more hop: fast-forward the wait timer
		# instead of sitting through the real four minutes
		[38.9, func(): pet._wait_remind = 239.8],
		[40.0, func(): store.state = "working"],
		[41.0, func(): pet._on_notice("sit", "该起来活动啦")],
		[45.5, func(): store.state = "done"],
	]


func _process(delta: float) -> void:
	t += delta
	while next_step < steps.size() and float(steps[next_step][0]) <= t:
		print("STEP %.2f" % t)
		(steps[next_step][1] as Callable).call()
		next_step += 1
	var sk = pet._rig.get_skeleton()
	var att := ""
	for slot_name in ["book", "pen", "fish"]:
		var s = sk.find_slot(slot_name)
		if s != null:
			var a = s.get_attachment()
			att += "%s:%s " % [slot_name, "nil" if a == null else "%.2f" % s.get_color().a]
	var line := "t=%.2f state=%s anim=%s chain=%s tail=%s present=%s queue=%d bookY=%.1f | %s" % [
		t, pet._state, pet._anim, str(pet._chain_clip), str(pet._chain_tail),
		pet._present_phase, pet._queue.size(), sk.find_bone("book").get_world_y(), att]
	if line.substr(line.find("state=")) != last_line:
		print(line)
		last_line = line.substr(line.find("state="))
	if t >= next_shot:
		next_shot += 1.0 / FPS
		pet._rig.update_skeleton(0.0)
		var img := await Stage.grab(vp)
		Stage.save_png(img, OUT + "/%05.1f.png" % t)
	if t > 38.9 and pet._anim == "needs_input_hop" and pet._state == "needs_input":
		wait_hop_seen = true
	if t >= END:
		if not wait_hop_seen:
			Stage.die("a long-parked needs_input never hopped again")
			return
		Stage.ok("playback timeline finished, frames in " + OUT)
