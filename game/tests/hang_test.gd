extends Node
## Dev-only: a run that never finishes, used to prove the harness can stop one.
##
## With the in-scene watchdog armed (3 s) the scene exits by itself with code 3;
## with a shorter external timeout (tools/testrun.py --timeout 2) the wrapper
## kills the process tree instead.  Either way nothing is left on the desktop.

const Stage = preload("res://tests/test_stage.gd")
const DEFAULT_HANG := 3.0


func _ready() -> void:
	var hang := DEFAULT_HANG
	var args := OS.get_cmdline_user_args()
	if args.size() > 0:
		if not String(args[0]).is_valid_float():
			Stage.die("hang time is not a number: '%s'" % args[0])
			return
		hang = float(args[0])
	Stage.begin(self, hang, "FishPet hang_test")
	print("HANG on purpose: watchdog fires in %.0f s" % hang)
	while true:
		await get_tree().process_frame
