extends Node
## App self-update check: compares the running version against a manifest in the
## repo and, when a newer build exists, downloads its installer to the user's
## Downloads folder.  The app never replaces itself — the user runs the
## downloaded installer by hand.
##
## Read-only over plain HTTPS (no git, no token, no proxy), and the manifest is
## read through jsDelivr's GitHub CDN exactly like the feed, so the same
## reachability assumptions apply.  The manifest lives at the repo root as
## `update.json`:
##
##     {"version": "0.1.0", "url": "https://.../FishPet.exe", "notes": "..."}
##
## `version` is the newest published build; `url` is its installer (empty means
## "a newer version exists but no build is published yet").  The running version
## comes from `application/config/version` in project.godot.

signal update_ready(path: String, version: String)
## A manual "检查更新" finished with nothing new / no installer yet / a failure.
## `message` is non-empty and human-readable; it stays empty for a new build,
## which is surfaced through `update_ready` instead.
signal update_checked(message: String)

const MANIFEST_URL := "https://cdn.jsdelivr.net/gh/JJbattle/PetFish@main/update.json"

## Overridable so the test harness can point at a fixture or drive _decide()
## without touching the network.
var manifest_url := MANIFEST_URL

var _http: HTTPRequest
var _dl_http: HTTPRequest
var _busy := false
var _manual := false
var _dl_path := ""
var _dl_version := ""


func _ready() -> void:
	_http = HTTPRequest.new()
	_http.timeout = 20.0
	_http.request_completed.connect(_on_manifest_done)
	add_child(_http)
	_dl_http = HTTPRequest.new()
	_dl_http.timeout = 120.0
	_dl_http.request_completed.connect(_on_download_done)
	add_child(_dl_http)


## The right-click menu "检查更新": fetch the manifest and, if a newer build has
## an installer, download it.  Everything is reported through update_ready /
## update_checked, never silently dropped.
func check_now() -> void:
	_manual = true
	if _busy:
		return
	_fetch_manifest()


func current_version() -> String:
	return str(ProjectSettings.get_setting("application/config/version", "0.0.0"))


func _fetch_manifest() -> void:
	_busy = true
	var err := _http.request(manifest_url)
	if err != OK:
		_busy = false
		_finish_manual("更新检查失败，请稍后再试")


func _on_manifest_done(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	if result != HTTPRequest.RESULT_SUCCESS or response_code != 200:
		_busy = false
		_finish_manual("更新检查失败，请稍后再试")
		return
	var decision := _decide(body.get_string_from_utf8())
	if decision.error != "":
		_busy = false
		_finish_manual(decision.error)
		return
	if not decision.newer:
		_busy = false
		_finish_manual("已经是最新版本")
		return
	if decision.url == "":
		_busy = false
		_finish_manual("发现新版本 v%s，安装包尚未发布" % decision.version)
		return
	_dl_version = decision.version
	_download(decision.url)


func _download(url: String) -> void:
	var dir := OS.get_system_dir(OS.SYSTEM_DIR_DOWNLOADS)
	_dl_path = dir.path_join("FishPet-v%s.exe" % _dl_version)
	_dl_http.download_file = _dl_path
	var err := _dl_http.request(url)
	if err != OK:
		_dl_path = ""
		_busy = false
		_finish_manual("下载失败，请稍后再试")


func _on_download_done(result: int, response_code: int, _headers: PackedStringArray, _body: PackedByteArray) -> void:
	_busy = false
	var path := _dl_path
	var ver := _dl_version
	_dl_path = ""
	_dl_version = ""
	if result == HTTPRequest.RESULT_SUCCESS and response_code == 200 and FileAccess.file_exists(path):
		_finish_manual()
		update_ready.emit(path, ver)
	else:
		if path != "" and FileAccess.file_exists(path):
			DirAccess.remove_absolute(path)
		_finish_manual("下载失败，请稍后再试")


## Network-free core: parse the manifest text and decide whether to download.
## Testable without the network (mirrors git_feed._ingest).  Returns a dict with
## `newer`, `version`, `url`, `notes` and `error` (empty when the text is valid).
func _decide(text: String) -> Dictionary:
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY:
		return {"newer": false, "version": "", "url": "", "notes": "", "error": "更新信息无法解析"}
	var version := str(data.get("version", "")).strip_edges()
	var url := str(data.get("url", "")).strip_edges()
	var notes := str(data.get("notes", "")).strip_edges()
	if version == "":
		return {"newer": false, "version": "", "url": url, "notes": notes, "error": "更新信息无法解析"}
	return {
		"newer": _is_newer(version, current_version()),
		"version": version, "url": url, "notes": notes, "error": "",
	}


## Plain x.y.z compare; a leading "v" is ignored.  Numeric segments are compared
## as numbers (so 0.1.10 > 0.1.9) and missing segments count as 0.
func _is_newer(candidate: String, current: String) -> bool:
	var a := candidate.trim_prefix("v").trim_prefix("V").split(".")
	var b := current.trim_prefix("v").trim_prefix("V").split(".")
	for i in maxi(a.size(), b.size()):
		var x := _part(a, i)
		var y := _part(b, i)
		if x != y:
			return x > y
	return false


func _part(parts: PackedStringArray, i: int) -> int:
	if i >= parts.size():
		return 0
	var s := parts[i].strip_edges()
	if s.is_valid_int():
		return s.to_int()
	return 0


func _finish_manual(message: String = "") -> void:
	if not _manual:
		return
	_manual = false
	if message != "":
		update_checked.emit(message)
