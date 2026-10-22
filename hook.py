# -*- coding: utf-8 -*-
"""Claude Code hook -> desktop pet state file.

Reads the hook payload from stdin and writes one JSON file per session under
``state/``.  The pet polls that directory.

IMPORTANT: this script must stay completely silent.  For ``UserPromptSubmit``
anything printed to stdout is injected into Claude's context.  Every failure
path therefore exits 0 without output.
"""

import json
import os
import sys
import tempfile
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_DIR = os.path.join(BASE_DIR, "state")

EVENT_STATE = {
    "SessionStart": "idle",
    "UserPromptSubmit": "working",
    "Stop": "done",
    "SessionEnd": "ended",
}


def read_payload():
    try:
        raw = sys.stdin.buffer.read()
    except Exception:
        return {}
    if not raw:
        return {}
    # Windows pipes often report gbk/cp936 for stdin; the payload is always utf-8.
    for enc in ("utf-8-sig", "utf-8", "gbk"):
        try:
            data = json.loads(raw.decode(enc))
            return data if isinstance(data, dict) else {}
        except Exception:
            continue
    return {}


def load_previous(path):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def atomic_write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)
        for _ in range(10):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                time.sleep(0.01)
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass


def prune(days=3):
    cutoff = time.time() - days * 86400
    try:
        names = os.listdir(STATE_DIR)
    except OSError:
        return
    for name in names:
        if not name.endswith(".json"):
            continue
        path = os.path.join(STATE_DIR, name)
        try:
            if os.path.getmtime(path) < cutoff:
                os.remove(path)
        except OSError:
            pass


def main():
    payload = read_payload()
    event = payload.get("hook_event_name") or ""
    if not event and len(sys.argv) > 1:
        event = sys.argv[1]

    sid = str(payload.get("session_id") or "unknown")
    now = time.time()
    path = os.path.join(STATE_DIR, sid + ".json")
    prev = load_previous(path)

    message = ""
    if event == "Notification":
        state = "needs_input"
        message = str(payload.get("message") or "")
    elif event in EVENT_STATE:
        state = EVENT_STATE[event]
    else:
        state = str(prev.get("state") or "idle")

    started_at = prev.get("started_at")
    finished_at = prev.get("finished_at")
    if state == "working":
        started_at = now
        finished_at = None
    elif state in ("done", "ended"):
        finished_at = now
        if started_at is None:
            started_at = now

    cwd = payload.get("cwd") or prev.get("cwd") or ""
    project = os.path.basename(cwd.rstrip("\\/")) if cwd else str(prev.get("project") or "")

    if state == "done":
        message = str(payload.get("last_assistant_message") or "")[:200]

    data = {
        "session_id": sid,
        "event": event,
        "state": state,
        "cwd": cwd,
        "project": project,
        "transcript_path": payload.get("transcript_path") or prev.get("transcript_path") or "",
        "message": message,
        "ts": now,
        "started_at": started_at,
        "finished_at": finished_at,
    }
    atomic_write(path, data)
    prune()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
