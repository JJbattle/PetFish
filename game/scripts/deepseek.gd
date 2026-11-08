extends Node
## Minimal DeepSeek chat client for the companion chat panel.
##
## Loads the API key from the DEEPSEEK_API_KEY environment variable or the
## user://secrets.json, then POSTs chat completions to DeepSeek's
## OpenAI-compatible endpoint.  The key never leaves this node except inside the
## Authorization header, and is never printed or logged.

signal chat_reply(text: String, error: String)

const ENDPOINT := "https://api.deepseek.com/chat/completions"
const MODEL := "deepseek-chat"

## Where the API key is persisted.  Test scenes point this at a per-process
## preview file so a "save key" test never overwrites the user's real key.
var secrets_path := "user://secrets.json"

var _http: HTTPRequest
var _api_key := ""
var _system_prompt := ""
var _busy := false


func _ready() -> void:
	_load_config()
	_http = HTTPRequest.new()
	_http.timeout = 60.0
	_http.request_completed.connect(_on_done)
	add_child(_http)


func has_key() -> bool:
	return _api_key != ""


## Store a new API key: updates the in-memory key and persists it to
## secrets.json.  The key is never returned or shown again, so once saved it
## cannot be copied or read back from the UI.
func set_api_key(key: String) -> void:
	_api_key = key.strip_edges()
	_save_secrets()


## Persist the current key (and any configured persona prompt) to secrets.json,
## preserving fields we did not touch.
func _save_secrets() -> void:
	var data: Dictionary = {}
	if FileAccess.file_exists(secrets_path):
		var file := FileAccess.open(secrets_path, FileAccess.READ)
		if file != null:
			var parsed = JSON.parse_string(file.get_as_text())
			if typeof(parsed) == TYPE_DICTIONARY:
				data = parsed
	data["api_key"] = _api_key
	if _system_prompt != "":
		data["system_prompt"] = _system_prompt
	var out := FileAccess.open(secrets_path, FileAccess.WRITE)
	if out == null:
		push_error("deepseek: cannot write %s" % secrets_path)
		return
	out.store_string(JSON.stringify(data))


## Loads the API key and an optional system prompt (the pet's persona). Both are
## optional: no key means the panel shows a hint, no prompt means no persona is
## injected and DeepSeek answers as a plain assistant. The prompt comes from the
## DEEPSEEK_SYSTEM_PROMPT environment variable or secrets.json's `system_prompt`.
func _load_config() -> void:
	_api_key = OS.get_environment("DEEPSEEK_API_KEY")
	_system_prompt = OS.get_environment("DEEPSEEK_SYSTEM_PROMPT")
	if FileAccess.file_exists(secrets_path):
		var file := FileAccess.open(secrets_path, FileAccess.READ)
		if file != null:
			var data = JSON.parse_string(file.get_as_text())
			if typeof(data) == TYPE_DICTIONARY:
				if _api_key == "":
					_api_key = str(data.get("api_key", ""))
				if _system_prompt == "":
					_system_prompt = str(data.get("system_prompt", ""))


func send(messages: Array) -> void:
	if _busy:
		return
	if _api_key == "":
		chat_reply.emit("", "还没有 API key。右键大肥鱼 → 提醒设置 →「AI 聊天」页填入密钥即可。")
		return
	var body: Array = []
	if _system_prompt != "":
		body.append({"role": "system", "content": _system_prompt})
	body.append_array(messages)
	var payload: String = JSON.stringify({"model": MODEL, "messages": body, "stream": false})
	var headers := PackedStringArray([
		"Content-Type: application/json",
		"Authorization: Bearer " + _api_key,
	])
	_busy = true
	var err := _http.request(ENDPOINT, headers, HTTPClient.METHOD_POST, payload)
	if err != OK:
		_busy = false
		chat_reply.emit("", "网络请求失败（错误码 %d）" % err)


func _on_done(result: int, response_code: int, _headers: PackedStringArray, body: PackedByteArray) -> void:
	_busy = false
	if result != HTTPRequest.RESULT_SUCCESS:
		chat_reply.emit("", "请求失败（错误码 %d）" % result)
		return
	var data = JSON.parse_string(body.get_string_from_utf8())
	if typeof(data) != TYPE_DICTIONARY:
		chat_reply.emit("", "响应解析失败")
		return
	if response_code != 200:
		var err_msg: String = "HTTP %d" % response_code
		var err_obj = data.get("error", {})
		if typeof(err_obj) == TYPE_DICTIONARY:
			err_msg = str(err_obj.get("message", err_msg))
		chat_reply.emit("", "DeepSeek 返回错误：%s" % err_msg)
		return
	var choices = data.get("choices", [])
	if typeof(choices) != TYPE_ARRAY or choices.is_empty():
		chat_reply.emit("", "DeepSeek 没有返回内容")
		return
	var first = choices[0]
	if typeof(first) != TYPE_DICTIONARY:
		chat_reply.emit("", "DeepSeek 返回格式异常")
		return
	var content: String = ""
	var msg_obj = first.get("message", {})
	if typeof(msg_obj) == TYPE_DICTIONARY:
		content = str(msg_obj.get("content", ""))
	chat_reply.emit(content, "")
