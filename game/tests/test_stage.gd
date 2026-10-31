extends Node
## Shared harness for the dev/verification scenes.
##
## The game is a borderless, always-on-top, per-pixel-transparent overlay; a test
## that simply instantiates main.tscn inherits all three, which leaves a topmost
## transparent window on the desktop that can swallow clicks if the run dies
## without reaching quit() (see PERFORMANCE_DIAGNOSIS_20261024.md).  So a test:
##   * puts the window it runs in back to a normal, non-topmost, bordered one,
##   * renders the pet inside a SubViewport, so the transparency needed for a
##     PNG happens there instead of in the desktop window,
##   * reports bad input with a non-zero exit instead of falling through, and
##   * arms a watchdog so a stuck await cannot sit on the screen forever.
##
## Usage from a scene script:
##   const Stage = preload("res://tests/test_stage.gd")
##   Stage.begin(6.0)                  # normal window + watchdog, call first
##   var vp := Stage.make_stage(Vector2i(760, 480))
##   await Stage.settled()
##   await Stage.shot(vp, "I:/.../out.png")

const PET_SCENE := "res://main.tscn"
const EXIT_BAD_INPUT := 2
const EXIT_WATCHDOG := 3


static func _tree() -> SceneTree:
	return Engine.get_main_loop() as SceneTree


## Print a clear failure and exit non-zero.  Nothing after this runs.
static func die(message: String, code: int = EXIT_BAD_INPUT) -> void:
	printerr("TEST FAIL: ", message)
	var tree := _tree()
	if tree != null:
		tree.quit(code)


## Quit at the end of a passing run.
static func ok(message: String = "") -> void:
	if message != "":
		print("TEST OK: ", message)
	var tree := _tree()
	if tree != null:
		tree.quit(0)


## Turn the window this test runs in into an ordinary one and arm the watchdog.
## Call once, at the top of _ready(), passing the scene's own node: the timer
## has to be parented to something already in the tree, and the root Window will
## not take children while the scene is still being set up.
static func begin(host: Node, watchdog_seconds: float = 60.0,
		caption: String = "FishPet test") -> void:
	var root := _tree().root
	if root != null:
		root.title = caption
		root.always_on_top = false
		root.borderless = false
		if "transparent" in root:
			root.transparent = false
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP, false)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_BORDERLESS, false)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT, false)
	DisplayServer.window_set_flag(DisplayServer.WINDOW_FLAG_RESIZE_DISABLED, false)
	# keep it out of the way of whatever the user is doing: top-left of the
	# usable area, small, and never focused on start
	DisplayServer.window_set_position(DisplayServer.screen_get_usable_rect().position
		+ Vector2i(40, 40))
	print("STAGE window always_on_top=",
		DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_ALWAYS_ON_TOP),
		" borderless=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_BORDERLESS),
		" transparent=", DisplayServer.window_get_flag(DisplayServer.WINDOW_FLAG_TRANSPARENT))
	var timer := Timer.new()
	timer.one_shot = true
	timer.wait_time = maxf(1.0, watchdog_seconds)
	timer.timeout.connect(func() -> void:
		printerr("TEST TIMEOUT after %.0f s" % watchdog_seconds)
		_tree().quit(EXIT_WATCHDOG))
	host.add_child(timer)
	timer.start()


## The pet, rendered into an offscreen SubViewport sized exactly to `size`.
## Its window is a texture in the middle of the real window; the pet itself is
## told not to touch window state (test_window).  `host` is the test scene's own
## node: the main Window refuses new children while it is still setting up the
## scene, so nothing may be added to the root from _ready().
static func make_stage(host: Node, size: Vector2i, show_in_window: bool = true) -> SubViewport:
	var vp := SubViewport.new()
	vp.name = "Stage"
	vp.size = size
	vp.transparent_bg = true
	vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	vp.disable_3d = true
	var pet = load(PET_SCENE).instantiate()
	pet.test_window = true
	vp.add_child(pet)
	host.add_child(vp)
	if show_in_window:
		show_stage_window(host, vp)
	return vp


## Plain blit of the stage into the (normal) window so the run can be watched.
static func show_stage_window(host: Node, vp: SubViewport) -> void:
	var rect := TextureRect.new()
	rect.name = "StageView"
	rect.texture = vp.get_texture()
	rect.texture_filter = CanvasItem.TEXTURE_FILTER_NEAREST
	rect.position = Vector2.ZERO
	rect.size = Vector2(vp.size)
	rect.mouse_filter = Control.MOUSE_FILTER_IGNORE
	host.add_child(rect)


## Two processed frames: enough for the rig to build and pose.
static func settled() -> void:
	await _tree().process_frame
	await _tree().process_frame


## Grab the stage as an RGBA image (alpha preserved).
static func grab(vp: SubViewport) -> Image:
	vp.render_target_update_mode = SubViewport.UPDATE_ONCE
	await RenderingServer.frame_post_draw
	await RenderingServer.frame_post_draw
	return vp.get_texture().get_image()


static func save_png(image: Image, path: String) -> void:
	DirAccess.make_dir_recursive_absolute(path.get_base_dir())
	var err := image.save_png(path)
	if err != OK:
		printerr("TEST FAIL: could not write ", path, " err=", err)
