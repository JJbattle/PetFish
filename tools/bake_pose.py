#!/usr/bin/env python3
"""Bake one animation frame into the setup pose so a static render can be split
per slot (the runtime re-applies slot timelines every frame, which defeats
set_attachment based isolation)."""
import json, os, shutil, sys

src = "game/assets/pet_spine"
dst = "game/tests/_pose"
anim_name = sys.argv[1] if len(sys.argv) > 1 else "drink_sip"
t = float(sys.argv[2]) if len(sys.argv) > 2 else 0.30

os.makedirs(dst, exist_ok=True)
for f in ("pet.atlas", "pet.png"):
    shutil.copyfile(os.path.join(src, f), os.path.join(dst, f))
d = json.load(open(os.path.join(src, "pet.spine-json"), encoding="utf-8"))
anim = d["animations"][anim_name]


def sample(keys, t):
    if not keys:
        return None
    if t <= keys[0]["time"]:
        return keys[0]
    for a, b in zip(keys, keys[1:]):
        if t <= b["time"]:
            f = (t - a["time"]) / max(1e-9, b["time"] - a["time"])
            out = {"time": t}
            for k in ("x", "y", "value"):
                if k in a or k in b:
                    out[k] = a.get(k, 0.0) + (b.get(k, 0.0) - a.get(k, 0.0)) * f
            for k in ("curve", "c2", "c3"):
                if k in a:
                    out[k] = a[k]
            return out
    return keys[-1]


bones = {b["name"]: b for b in d["bones"]}
for name, ch in anim.get("bones", {}).items():
    b = bones[name]
    for kind, keys in ch.items():
        k = sample(keys, t)
        if kind == "translate":
            b["x"] = b.get("x", 0.0) + k.get("x", 0.0)
            b["y"] = b.get("y", 0.0) + k.get("y", 0.0)
        elif kind == "rotate":
            b["rotation"] = b.get("rotation", 0.0) + k.get("value", 0.0)
        elif kind == "scale":
            b["scaleX"] = b.get("scaleX", 1.0) * k.get("x", 1.0)
            b["scaleY"] = b.get("scaleY", 1.0) * k.get("y", 1.0)

slots = {s["name"]: s for s in d["slots"]}
for name, ch in anim.get("slots", {}).items():
    keys = ch.get("attachment")
    if keys:
        k = sample(keys, t)
        if "name" in k:
            slots[name]["attachment"] = k["name"]
        else:
            slots[name].pop("attachment", None)

d["animations"] = {}
with open(os.path.join(dst, "pet.spine-json"), "w", encoding="utf-8", newline="\n") as fh:
    json.dump(d, fh, ensure_ascii=False, separators=(",", ":"))
print("baked", anim_name, "at", t, "->", dst)
