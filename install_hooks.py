# -*- coding: utf-8 -*-
"""Merge the fishpet hooks into the user-level Claude Code settings.

Idempotent: re-running replaces the fishpet handlers instead of duplicating
them.  Always writes a timestamped backup first and never prints the file
contents (it contains the API token).

    python install_hooks.py            # install / refresh
    python install_hooks.py --remove   # uninstall
    python install_hooks.py --dry-run  # show the resulting hooks block
"""

import json
import os
import shutil
import sys
import time

SETTINGS = os.path.join(os.path.expanduser("~"), ".claude", "settings.json")
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
HOOK_PATH = os.path.join(BASE_DIR, "hook.py")
# Quoted backslash paths are the only form that works identically in cmd.exe,
# PowerShell and Git Bash (the hook runner differs between installs).
PYTHON = r"C:\Windows\py.exe"
COMMAND = '"%s" -3 "%s"' % (PYTHON, HOOK_PATH)


def is_ours(command):
    # Case-insensitive: the project directory may be ".claude/fishpet" or "PetFish".
    return "fishpet" in command.lower() and "hook.py" in command

EVENTS = ["SessionStart", "UserPromptSubmit", "Stop", "SessionEnd"]
NOTIFICATION_MATCHERS = ["permission_prompt", "idle_prompt"]


def handler():
    return {"type": "command", "command": COMMAND, "timeout": 5}


def strip_ours(entries):
    """Remove every fishpet handler from an event's entry list."""
    kept = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        hooks = [
            h for h in entry.get("hooks", [])
            if not (isinstance(h, dict) and is_ours(str(h.get("command", ""))))
        ]
        if hooks:
            entry = dict(entry)
            entry["hooks"] = hooks
            kept.append(entry)
        elif "hooks" not in entry:
            kept.append(entry)
    return kept


def build(existing):
    hooks = dict(existing) if isinstance(existing, dict) else {}
    for event in EVENTS:
        hooks[event] = strip_ours(hooks.get(event)) + [{"hooks": [handler()]}]
    entries = strip_ours(hooks.get("Notification"))
    for matcher in NOTIFICATION_MATCHERS:
        entries.append({"matcher": matcher, "hooks": [handler()]})
    hooks["Notification"] = entries
    return hooks


def main(argv):
    remove = "--remove" in argv
    dry_run = "--dry-run" in argv

    if not os.path.isfile(SETTINGS):
        print("settings not found:", SETTINGS)
        return 1
    with open(SETTINGS, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    if remove:
        current = data.get("hooks")
        if isinstance(current, dict):
            for event in list(current):
                current[event] = strip_ours(current[event])
                if not current[event]:
                    del current[event]
            if not current:
                data.pop("hooks", None)
    else:
        data["hooks"] = build(data.get("hooks"))

    if dry_run:
        print(json.dumps({"hooks": data.get("hooks")}, indent=2))
        return 0

    backup = SETTINGS + ".bak." + time.strftime("%Y%m%d-%H%M%S")
    shutil.copy2(SETTINGS, backup)

    tmp = SETTINGS + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.replace(tmp, SETTINGS)

    # Verify the round trip before declaring success.
    with open(SETTINGS, "r", encoding="utf-8") as fh:
        check = json.load(fh)
    assert "env" in check, "env block disappeared"
    print(("%s hooks; backup: %s" % ("removed" if remove else "installed", backup)))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
