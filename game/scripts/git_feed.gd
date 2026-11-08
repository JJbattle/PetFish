extends Node
## Weekly feed sync: pulls the current week's message from a public git repo and
## emits `feed_ready` when it holds content that has not been seen yet.
##
## Read-only by design: it fetches the file over plain HTTPS (no git binary, no
## account, no token, no proxy), so any machine running the pet syncs with zero
## setup.  Each week gets its own file at `weekly/<monday>.txt`, where <monday>
## is the date of that week's Monday (e.g. 2026-11-02 for the week of 2026-11-05);
## the pet only ever asks for this week's file, so history stays in the repo
## without ever being pulled down.
##
## Two things make this work out of the box:
##   * The source is read through jsDelivr's GitHub CDN (cdn.jsdelivr.net), which
##     is reachable where raw.githubusercontent.com is flaky or blocked.
##   * Godot ships no usable CA trust store, so HTTPS fails certificate
##     verification otherwise.  project.godot sets
##     `network/tls/certificate_bundle_override` to the bundled Mozilla CA list
##     (res://assets/cacert.pem).

signal feed_ready(text: String)
## A manual "检查更新" finished with nothing new (or a transient failure).  `text`
## is the human-readable result to surface; it is empty for new content, which is
## already surfaced through `feed_ready`.
signal feed_checked(text: String)

## %s is the current week's Monday, formatted YYYY-MM-DD.
const RAW_TEMPLATE := "https://cdn.jsdelivr.net/gh/JJbattle/fish-feed@main/weekly/%s.txt"
const DATA_PATH := "user://data/feed.json"
const INTERVAL := 3600.0
const TICK := 1.0

## Overridable so the test harness can use a throwaway profile.
var data_path := DATA_PATH

var _http: HTTPRequest
var _busy := false
var _last_hash := ""
var _tick := 0.0
var _next_fetch := 0.0
## Set while a fetch was requested by the user (menu "检查更新"), so its outcome
## is reported back through `feed_checked` instead of being silently dropped.
var _manual := false


func _ready() -> void:
	_load()
	_http = HTTPRequest.new()
	_http.timeout = 20.0
	_http.request_completed.connect(_on_done)
	add_child(_http)
	# First poll runs on the first tick, not an hour after launch.
	_next_fetch = 0.0


func _process(delta: float) -> void:
	_tick += delta
	if _tick < TICK:
		return
	_tick = 0.0
	if _busy:
		return
	if Time.get_unix_time_from_system() >= _next_fetch:
		_fetch()


## The date of the current week's Monday as YYYY-MM-DD.  Computed from the local
## civil date (the same way reminders._weekday does) so it does not depend on how
## Godot encodes `weekday` in a date dictionary.
## Pull the week's feed now, on demand (the right-click "检查更新").  The result
## is reported through `feed_ready` when new content arrives, or `feed_checked`
## when there is nothing new / the fetch failed.  If an automatic poll is already
## in flight, its outcome is reused as this check's result.
func check_now() -> void:
	_manual = true
	if _busy:
		return
	_fetch()


func week_monday() -> String:
	var dt := Time.get_datetime_dict_from_system()
	var midnight := Time.get_unix_time_from_datetime_dict({
		"year": int(dt["year"]), "month": int(dt["month"]), "day": int(dt["day"]),
		"hour": 0, "minute": 0, "second": 0,
	})
	var weekday := (int(midnight / 86400.0) + 4) % 7  # 0=Sunday .. 6=Saturday
	var monday_ts := midnight - ((weekday + 6) % 7) * 86400
	var md := Time.get_datetime_dict_from_unix_time(monday_ts)
	return "%04d-%02d-%02d" % [int(md["year"]), int(md["month"]), int(md["day"])]


func _fetch() -> void:
	_next_fetch = Time.get_unix_time_from_system() + INTERVAL
	_busy = true
	var url := RAW_TEMPLATE % week_monday()
	var err := _http.request(url)
	if err != OK:
		_busy = false
		# Transient failure (offline, proxy down, ...): retry in a minute.
		_next_fetch = Time.get_unix_time_from_system() + 60.0
		_finish_manual("更新失败，请稍后再试")


func _on_done(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_busy = false
	if result != HTTPRequest.RESULT_SUCCESS:
		_finish_manual("更新失败，请稍后再试")
		return
	if response_code == 404:
		# No file for this week yet; the hourly poll keeps retrying.
		_finish_manual("这周还没有新内容")
		return
	if response_code != 200:
		_finish_manual("更新失败，请稍后再试")
		return
	if _ingest(body.get_string_from_utf8()):
		# New content is already surfaced through feed_ready; nothing more to say.
		_finish_manual()
	else:
		_finish_manual("没有可同步的新内容")


## Report the outcome of a manual check, if one was pending.  `message` is empty
## when the check found new content (already handled by `feed_ready`).
func _finish_manual(message: String = "") -> void:
	if not _manual:
		return
	_manual = false
	if message != "":
		feed_checked.emit(message)


## Core, network-free: decide whether `text` is new content and emit if so.  The
## test harness calls this directly so it never needs to reach the network.
## Returns true when the content was new (and `feed_ready` was emitted).
func _ingest(text: String) -> bool:
	text = text.strip_edges()
	if text == "":
		return false
	var hash := text.sha256_text()
	if hash == _last_hash:
		return false
	_last_hash = hash
	_save()
	feed_ready.emit(text)
	return true


func _save() -> void:
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(data_path.get_base_dir()))
	var file := FileAccess.open(data_path, FileAccess.WRITE)
	if file == null:
		push_warning("feed: cannot write " + data_path)
		return
	file.store_string(JSON.stringify({"last_hash": _last_hash}, "\t"))
	file.close()


func _load() -> void:
	if not FileAccess.file_exists(data_path):
		return
	var file := FileAccess.open(data_path, FileAccess.READ)
	if file == null:
		return
	var raw = JSON.parse_string(file.get_as_text())
	file.close()
	if typeof(raw) == TYPE_DICTIONARY:
		_last_hash = str(raw.get("last_hash", ""))
