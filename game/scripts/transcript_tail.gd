extends RefCounted
## Incremental reader for a Claude Code transcript (*.jsonl).
##
## Only the newly appended bytes are read, and only complete lines are parsed
## (a line still being written is left for the next poll).  Transcripts can grow
## to several megabytes per session, so the reader is capped and never walks the
## whole file.
##
## We deliberately surface only the tool name and a short, safe detail: never
## tool output, which could contain source code or credentials.

const MAX_READ := 524288
const MIN_LINE_LEN := 20

var path := ""
var offset := 0

var tool_name := ""
var detail := ""
var tool_count := 0
var last_tool_unix := 0.0


func set_path(new_path: String) -> void:
	if new_path == path:
		return
	path = new_path
	offset = 0
	tool_name = ""
	detail = ""
	tool_count = 0
	last_tool_unix = 0.0


func poll() -> void:
	if path == "" or not FileAccess.file_exists(path):
		return
	var f := FileAccess.open(path, FileAccess.READ)
	if f == null:
		return
	var size := f.get_length()
	if size < offset:
		# File was truncated / replaced.
		offset = 0
	if size <= offset:
		return

	var start := offset
	if size - start > MAX_READ:
		start = size - MAX_READ
	f.seek(start)
	var buf := f.get_buffer(size - start)
	if buf.is_empty():
		return

	var cut := -1
	for i in range(buf.size() - 1, -1, -1):
		if buf[i] == 10:  # '\n'
			cut = i
			break
	if cut < 0:
		# No complete line yet; read again next poll.
		offset = start
		return

	var body := buf.slice(0, cut).get_string_from_utf8()
	offset = start + cut + 1

	for line in body.split("\n"):
		if line.length() < MIN_LINE_LEN:
			continue
		if not "\"tool_use\"" in line:
			continue
		_consume_line(line)


func _consume_line(line: String) -> void:
	var data = JSON.parse_string(line)
	if typeof(data) != TYPE_DICTIONARY:
		return
	if str(data.get("type", "")) != "assistant":
		return
	var message = data.get("message", {})
	if typeof(message) != TYPE_DICTIONARY:
		return
	var content = message.get("content", [])
	if typeof(content) != TYPE_ARRAY:
		return

	var line_ts := _iso_to_unix(str(data.get("timestamp", "")))
	for block in content:
		if typeof(block) != TYPE_DICTIONARY or str(block.get("type", "")) != "tool_use":
			continue
		var name := str(block.get("name", ""))
		if name == "":
			continue
		tool_name = name
		tool_count += 1
		var input = block.get("input", {})
		detail = _detail_for(name, input if typeof(input) == TYPE_DICTIONARY else {})
		if line_ts > 0.0:
			last_tool_unix = line_ts


func _detail_for(tool: String, input: Dictionary) -> String:
	match tool:
		"Edit", "Write", "Read", "NotebookEdit":
			var file := str(input.get("file_path", ""))
			return file.get_file() if file != "" else tool
		"Bash":
			var desc := str(input.get("description", ""))
			return desc if desc != "" else "运行命令"
		"Grep", "Glob":
			var pattern := str(input.get("pattern", ""))
			return ("找 " + pattern).substr(0, 26) if pattern != "" else "搜索文件"
		"Agent":
			var agent_desc := str(input.get("description", ""))
			return agent_desc if agent_desc != "" else "分身干活"
		"WebFetch", "WebSearch":
			return "查资料"
		"TodoWrite":
			return "更新清单"
		"Skill":
			return "用技能 " + str(input.get("skill", ""))
	return tool


static func _iso_to_unix(text: String) -> float:
	if text.length() < 19:
		return 0.0
	var parts := {
		"year": int(text.substr(0, 4)),
		"month": int(text.substr(5, 2)),
		"day": int(text.substr(8, 2)),
		"hour": int(text.substr(11, 2)),
		"minute": int(text.substr(14, 2)),
		"second": int(text.substr(17, 2)),
	}
	return float(Time.get_unix_time_from_datetime_dict(parts))
