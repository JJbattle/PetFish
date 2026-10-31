#!/usr/bin/env python3
"""Build the Spine 4.2 rig used by the desktop pet.

The source is a single front-view illustration.  We keep the body as one
dense, smoothly weighted mesh (so hair and cloth bend without seams), cut the
whale tail out as its own mesh on a small bone chain, and write:

    pet.png         atlas page (body + tail)
    pet.atlas       Spine atlas
    pet.spine-json  Spine 4.2 JSON skeleton + meshes + animations

Pure Pillow: no numpy/opencv needed.  The source artwork is CC BY-NC-SA 4.0
(see assets/art/ATTRIBUTION.md); this script never touches the network.

Usage:
    python tools/build_spine.py --src assets/art/pet_portrait.png \
        --out game/assets/pet_spine --debug tools/_debug
"""

from __future__ import annotations

import argparse
import json
import math
import os
from collections import deque

from PIL import Image, ImageDraw, ImageFilter

# ---------------------------------------------------------------- geometry

SRC_CX = 500.0          # character centre line in the source image
SRC_BOTTOM = 952.0      # sole of the feet in the source image
PAD = 24                # transparent margin around the character
GRID = 8.0              # body/tail mesh spacing in source pixels
TAIL_GROW = 2           # pixels of outline kept around the tail fill
INPAINT_DEPTH = 14      # pixels of body reconstructed under the tail

# Exact visible silhouette of the whale tail (source pixels), hand-traced from
# the artwork.  The tail is *behind* the hair and the skirt ruffle, so it is
# drawn under the body; the body keeps every pixel that overlaps the tail.
TAIL_POLYGON = [
    (572, 810), (586, 813), (600, 815), (614, 816), (628, 815), (642, 812),
    (655, 809), (667, 805), (678, 800), (690, 794), (702, 791), (715, 789),
    (728, 786), (741, 781), (753, 774), (764, 765), (774, 754), (783, 741),
    (790, 727), (795, 713), (798, 699), (799, 685), (797, 674), (793, 666),
    (790, 664), (786, 668), (777, 675), (766, 684), (755, 695), (745, 706),
    (737, 717), (731, 718), (722, 709), (712, 698), (702, 686), (692, 675),
    (684, 666), (678, 661), (672, 664), (665, 672), (658, 683), (652, 695),
    (647, 707), (643, 719), (641, 730), (642, 743), (645, 755), (647, 767),
    (642, 777), (633, 785), (622, 790), (610, 794), (596, 797), (582, 799),
    (572, 804),
]

# name, parent, world x, world y  (world is y-up, origin at the feet centre)
BONES = [
    ("root", None, 0.0, 0.0),
    ("hip", "root", 0.0, 252.0),
    ("spine", "hip", 0.0, 332.0),
    ("chest", "spine", 0.0, 382.0),
    ("neck", "chest", 0.0, 447.0),
    ("head", "neck", 0.0, 472.0),
    ("hairL1", "head", -160.0, 452.0),
    ("hairL2", "hairL1", -190.0, 312.0),
    ("hairL3", "hairL2", -210.0, 182.0),
    ("hairR1", "head", 160.0, 452.0),
    ("hairR2", "hairR1", 200.0, 312.0),
    ("hairR3", "hairR2", 220.0, 182.0),
    ("ahoge1", "head", -35.0, 747.0),
    ("ahoge2", "ahoge1", -80.0, 792.0),
    ("finL", "head", -200.0, 517.0),
    ("finR", "head", 200.0, 517.0),
    ("eyeL", "head", -75.0, 520.0),
    ("eyeR", "head", 75.0, 520.0),
    ("tail1", "hip", 170.0, 182.0),
    ("tail2", "tail1", 190.0, 217.0),
    ("tailFin", "tail2", 195.0, 252.0),
    ("skirt", "hip", 0.0, 192.0),
]
BONE_WORLD = {name: (x, y) for name, _parent, x, y in BONES}
BONE_INDEX = {name: i for i, (name, _p, _x, _y) in enumerate(BONES)}


def clamp01(v: float) -> float:
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def smoothstep(a: float, b: float, v: float) -> float:
    if a == b:
        return 1.0 if v >= b else 0.0
    t = clamp01((v - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def img_to_world(x: float, y: float) -> tuple[float, float]:
    return (x - SRC_CX, SRC_BOTTOM - y)


# ---------------------------------------------------------------- art prep


def prepare_art(src: Image.Image, debug_dir: str | None):
    im = src.convert("RGBA")
    alpha = im.getchannel("A")
    bbox = alpha.getbbox()
    if bbox is None:
        raise SystemExit("source image is empty")
    x0 = max(0, bbox[0] - PAD)
    y0 = max(0, bbox[1] - PAD)
    x1 = min(im.width, bbox[2] + PAD)
    y1 = min(im.height, bbox[3] + PAD)
    crop_box = (x0, y0, x1, y1)

    # Mask image in source coordinates: the exact visible tail silhouette,
    # minus fully transparent source pixels, plus one pixel of outline.
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).polygon(TAIL_POLYGON, fill=255)
    mask = mask.filter(ImageFilter.MaxFilter(TAIL_GROW * 2 + 1))
    mp = mask.load()
    alpha_px = im.load()
    for y in range(im.height):
        for x in range(im.width):
            if mp[x, y] == 0:
                continue
            r, g, b, a = alpha_px[x, y]
            hi, lo = max(r, g, b), min(r, g, b)
            # Keep transparent (nothing to cut), warm cloth or skin, and pale
            # desaturated ruffle shading that the polygon grazed.
            if (a <= 8
                    or (r > b + 6 and hi > 60)
                    or (hi > 120 and hi - lo < 40)):
                mp[x, y] = 0
    if mask.getbbox() is None:
        raise SystemExit("tail mask is empty")
    # The tail stays part of the body texture: the mesh bends it in place.
    # A separate tail layer would need its own transform and draw order; one
    # mesh keeps the rest pose pixel-exact.
    body = im.crop(crop_box)
    sp = im.load()

    # Tail influence fades outward so the skirt/hair edge bends with the fin
    # instead of shearing away from it.
    tail_near = mask.filter(ImageFilter.MaxFilter(9))
    tail_mid = mask.filter(ImageFilter.MaxFilter(21))
    tail_far = mask.filter(ImageFilter.MaxFilter(33))

    # ---- classification masks on the body (source coords)
    def is_blue(r, g, b):
        return b > 150 and b > r * 1.25 and b > g * 1.10

    def is_fin(r, g, b, a):
        if a < 40:
            return False
        mx, mn = max(r, g, b), min(r, g, b)
        v = mx / 255.0
        s = 0.0 if mx == 0 else (mx - mn) / mx
        return v > 0.75 and s < 0.38

    hair_core = Image.new("L", im.size, 0)
    fin_core = Image.new("L", im.size, 0)
    ahoge_core = Image.new("L", im.size, 0)
    hp, fp, ap = hair_core.load(), fin_core.load(), ahoge_core.load()
    for y in range(crop_box[1], crop_box[3]):
        for x in range(crop_box[0], crop_box[2]):
            if mp[x, y] > 0:
                continue
            r, g, b, a = sp[x, y]
            if a < 40:
                continue
            if y > 460 and is_blue(r, g, b):
                hp[x, y] = 255
            if 380 <= y <= 500 and (x < 315 or x > 685) and is_fin(r, g, b, a):
                fp[x, y] = 255
            if 125 <= y <= 240 and 315 <= x <= 510 and is_blue(r, g, b):
                ap[x, y] = 255
    hair_mask = hair_core.filter(ImageFilter.MaxFilter(9))
    fin_mask = fin_core.filter(ImageFilter.MaxFilter(7))
    ahoge_mask = ahoge_core.filter(ImageFilter.MaxFilter(7))

    if debug_dir:
        os.makedirs(debug_dir, exist_ok=True)
        _save_preview(body, os.path.join(debug_dir, "body.png"))
        _save_mask(im, mp, os.path.join(debug_dir, "tail_mask.png"))
        _save_mask(im, hair_mask.load(), os.path.join(debug_dir, "hair_mask.png"))

    return {
        "body": body,
        "crop_box": crop_box,
        "tail_mask": mask,
        "tail_near": tail_near,
        "tail_mid": tail_mid,
        "tail_far": tail_far,
        "hair_mask": hair_mask,
        "fin_mask": fin_mask,
        "ahoge_mask": ahoge_mask,
    }


def _save_preview(im: Image.Image, path: str) -> None:
    bg = Image.new("RGBA", im.size, (255, 0, 255, 255))
    bg.alpha_composite(im)
    bg.convert("RGB").save(path)


def _save_mask(src: Image.Image, mask, path: str) -> None:
    vis = Image.new("RGBA", src.size, (255, 0, 255, 255))
    vis.alpha_composite(src)
    vp = vis.load()
    for y in range(src.height):
        for x in range(src.width):
            if mask[x, y] > 0:
                vp[x, y] = (0, 255, 0, 255)
    vis.convert("RGB").save(path)


# ---------------------------------------------------------------- weights


def base_weights(y: float) -> dict[str, float]:
    """Torso chain weights by image y (before hair/fin/eye overrides)."""
    if y <= 460:
        return {"head": 1.0}
    if y <= 510:
        t = (y - 460) / 50.0
        return {"head": 1 - t, "neck": t}
    if y <= 560:
        t = (y - 510) / 50.0
        return {"neck": 1 - t, "chest": t}
    if y <= 610:
        return {"chest": 1.0}
    if y <= 670:
        t = (y - 610) / 60.0
        return {"chest": 1 - t, "spine": t}
    if y <= 710:
        t = (y - 670) / 40.0
        return {"spine": 1 - t, "hip": t}
    if y <= 810:
        t = (y - 710) / 100.0
        return {"hip": 1 - t, "skirt": t}
    if y <= 890:
        t = (y - 810) / 80.0
        return {"skirt": 1 - t, "root": t}
    return {"root": 1.0}


def mask_hit(mask: Image.Image, x: float, y: float, radius: int) -> bool:
    xi, yi = int(round(x)), int(round(y))
    if (xi + radius < 0 or yi + radius < 0
            or xi - radius >= mask.width or yi - radius >= mask.height):
        return False
    p = mask.load()
    for yy in range(max(0, yi - radius), min(mask.height, yi + radius + 1)):
        for xx in range(max(0, xi - radius), min(mask.width, xi + radius + 1)):
            if p[xx, yy] > 0:
                return True
    return False


def hair_weights(y: float) -> dict[str, float]:
    f1 = clamp01((650.0 - y) / 150.0)
    f3 = clamp01((y - 650.0) / 130.0)
    f2 = max(0.0, 1.0 - f1 - f3)
    total = f1 + f2 + f3
    if total <= 0.0:
        return {"hairL1": 1.0}
    return {"hairL1": f1 / total, "hairL2": f2 / total, "hairL3": f3 / total}


def body_vertex_weights(x: float, y: float, art) -> dict[str, float]:
    w = base_weights(y)

    # ---- eyes: squash around the eye centre for the blink
    for name, cx in (("eyeL", 425.0), ("eyeR", 575.0)):
        r = math.hypot((x - cx) / 52.0, (y - 432.0) / 39.0)
        amt = 1.0 - smoothstep(0.70, 1.08, r)
        if amt > 0.001:
            w = {k: v * (1 - amt) for k, v in w.items()}
            w[name] = w.get(name, 0.0) + amt

    # ---- ear fins
    fin_amt = 0.0
    if 380 <= y <= 500 and (x < 320 or x > 680):
        fin_amt = clamp01((abs(x - 500.0) - 205.0) / 55.0)
        fin_amt *= clamp01((y - 380.0) / 15.0)
        fin_amt *= 1.0 - clamp01((y - 480.0) / 20.0)
        if not mask_hit(art["fin_mask"], x, y, 4):
            fin_amt = 0.0
    if fin_amt > 0.001:
        name = "finL" if x < 500 else "finR"
        w = {k: v * (1 - fin_amt) for k, v in w.items()}
        w[name] = w.get(name, 0.0) + fin_amt

    # ---- ahoge (the little blue loop above the bonnet)
    ah_amt = 0.0
    if 125 <= y <= 240 and 315 <= x <= 510:
        ah_amt = clamp01((235.0 - y) / 20.0)
        if not mask_hit(art["ahoge_mask"], x, y, 6):
            ah_amt = 0.0
    if ah_amt > 0.001:
        w2 = clamp01((185.0 - y) / 40.0)
        w1 = 1.0 - w2
        w = {k: v * (1 - ah_amt) for k, v in w.items()}
        w["ahoge1"] = w.get("ahoge1", 0.0) + ah_amt * w1
        w["ahoge2"] = w.get("ahoge2", 0.0) + ah_amt * w2

    # ---- long side hair (only well away from the face/arms)
    side = max(clamp01((360.0 - x) / 15.0), clamp01((x - 640.0) / 15.0))
    if side > 0.0 and y > 462:
        hair_amt = side * clamp01((y - 462.0) / 55.0)
        if hair_amt > 0.001 and mask_hit(art["hair_mask"], x, y, 5):
            chain = hair_weights(y)
            prefix = "hairL" if x < 500 else "hairR"
            w = {k: v * (1 - hair_amt) for k, v in w.items()}
            for key, value in chain.items():
                bone = prefix + key[-1]  # hairL1 / hairR2 ...
                w[bone] = w.get(bone, 0.0) + hair_amt * value

    # ---- tail: the fin lives on the same mesh, so it is bent in place.  The
    # influence fades over ~20px into the skirt so the two never tear apart.
    tail_amt = tail_influence(x, y, art)
    if tail_amt > 0.001:
        chain = tail_vertex_weights(x, y)
        w = {k: v * (1 - tail_amt) for k, v in w.items()}
        for key, value in chain.items():
            w[key] = w.get(key, 0.0) + tail_amt * value

    total = sum(w.values())
    if total <= 0.0:
        return {"root": 1.0}
    return {k: v / total for k, v in w.items() if v > 0.0005}


def tail_influence(x: float, y: float, art) -> float:
    """1 inside the visible tail, fading to 0 over the surrounding ~20px."""
    xi, yi = int(round(x)), int(round(y))

    def hit(img: Image.Image, radius: int) -> bool:
        if xi + radius < 0 or yi + radius < 0:
            return False
        if xi - radius >= img.width or yi - radius >= img.height:
            return False
        p = img.load()
        for yy in range(max(0, yi - radius), min(img.height, yi + radius + 1)):
            for xx in range(max(0, xi - radius), min(img.width, xi + radius + 1)):
                if p[xx, yy] > 0:
                    return True
        return False

    if hit(art["tail_mask"], 0):
        return 1.0
    if hit(art["tail_near"], 2):
        return 0.72
    if hit(art["tail_mid"], 3):
        return 0.42
    if hit(art["tail_far"], 4):
        return 0.18
    return 0.0


def tail_vertex_weights(x: float, y: float) -> dict[str, float]:
    fin_w = clamp01((730.0 - y) / 40.0)
    stem_w = clamp01((y - 745.0) / 40.0)
    mid_w = max(0.0, 1.0 - fin_w - stem_w)
    w = {"tail1": stem_w, "tail2": mid_w, "tailFin": fin_w}
    total = sum(w.values())
    if total <= 0.0:
        return {"tail1": 1.0}
    return {k: v / total for k, v in w.items() if v > 0.0005}


# ---------------------------------------------------------------- meshes


def build_mesh(rect, weight_fn, art=None, name=""):
    """Return (uvs, triangles, vertices, flat_weighted) for a grid mesh."""
    x0, y0, x1, y1 = rect
    cols = int(math.ceil((x1 - x0) / GRID)) + 1
    rows = int(math.ceil((y1 - y0) / GRID)) + 1
    xs = [min(x0 + i * GRID, x1) for i in range(cols)]
    ys = [min(y0 + j * GRID, y1) for j in range(rows)]

    uvs = []
    verts = []
    for y in ys:
        for x in xs:
            uvs.append(round((x - x0) / (x1 - x0), 6))
            uvs.append(round(1.0 - (y - y0) / (y1 - y0), 6))
            weights = weight_fn(x, y)
            wx, wy = img_to_world(x, y)
            entry = []
            for bone, amount in sorted(weights.items(), key=lambda kv: -kv[1]):
                bx, by = BONE_WORLD[bone]
                entry.append((BONE_INDEX[bone], wx - bx, wy - by, amount))
            verts.append(entry)

    triangles = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a = j * cols + i
            b = a + 1
            c = a + cols
            d = c + 1
            triangles.extend((a, c, d, a, d, b))

    flat = []
    for entry in verts:
        total = sum(e[3] for e in entry)
        if total <= 0.0:
            entry = [(0, 0.0, 0.0, 1.0)]
            total = 1.0
        entry = [e for e in entry if e[3] / total > 0.008][:4]
        total = sum(e[3] for e in entry)
        flat.append(len(entry))
        for bone, bx, by, amount in entry:
            flat.extend((bone, round(bx, 3), round(by, 3), round(amount / total, 4)))
    return uvs, triangles, flat, verts, xs, ys, cols, rows


# ---------------------------------------------------------------- animation


def keys_sine(duration: float, amp: float, phase: float = 0.0, n: int = 8, base: float = 0.0):
    out = []
    for i in range(n + 1):
        t = duration * i / n
        v = base + amp * math.sin(2.0 * math.pi * i / n + phase)
        out.append((t, v))
    return out


def rotate_keys(duration, amp, phase=0.0, n=8, base=0.0):
    return [{"time": round(t, 3), "value": round(v, 3)} for t, v in keys_sine(duration, amp, phase, n, base)]


def translate_keys(duration, ax, ay, phase=0.0, n=8, base_x=0.0, base_y=0.0):
    out = []
    for i in range(n + 1):
        t = duration * i / n
        out.append({"time": round(t, 3),
                    "x": round(base_x + ax * math.sin(2 * math.pi * i / n + phase), 3),
                    "y": round(base_y + ay * math.sin(2 * math.pi * i / n + phase), 3)})
    return out


def scale_keys(duration, sx, sy, phase=0.0, n=8):
    out = []
    for i in range(n + 1):
        t = duration * i / n
        out.append({"time": round(t, 3),
                    "x": round(sx[i], 4) if isinstance(sx, list) else round(1.0 + sx * math.sin(2 * math.pi * i / n + phase), 4),
                    "y": round(sy[i], 4) if isinstance(sy, list) else round(1.0 + sy * math.sin(2 * math.pi * i / n + phase), 4)})
    return out


def blink_keys(duration, at, closed=0.14):
    """Bone scale timeline that closes and opens the eyes once."""
    return [
        {"time": round(max(0.0, at - 0.08), 3), "x": 1.0, "y": 1.0},
        {"time": round(at, 3), "x": 1.0, "y": closed},
        {"time": round(at + 0.08, 3), "x": 1.0, "y": closed},
        {"time": round(at + 0.16, 3), "x": 1.0, "y": 1.0},
    ]


def multi_blink_keys(duration, times, closed=0.14):
    """Several blinks in one loop; times must be at least 0.2 s apart."""
    out = []
    for at in times:
        if at + 0.16 < duration:
            out.extend(blink_keys(duration, at, closed))
    out.sort(key=lambda k: k["time"])
    return out


def scalar_keys(pairs):
    """[(time, value)] -> a rotate timeline."""
    return [{"time": round(t, 3), "value": round(v, 3)} for t, v in pairs]


def xy_keys(pairs):
    """[(time, x, y)] -> a translate or scale timeline."""
    return [{"time": round(t, 3), "x": round(x, 4), "y": round(y, 4)} for t, x, y in pairs]


def build_animations():
    anims = {}

    # ---- idle: 4 s breathing loop
    T = 4.0
    anims["idle"] = {"bones": {
        "root": {"translate": translate_keys(T, 0.0, 2.2)},
        "chest": {"scale": scale_keys(T, 0.006, 0.010)},
        "spine": {"rotate": rotate_keys(T, 0.5)},
        "neck": {"rotate": rotate_keys(T, 0.6)},
        "head": {"rotate": rotate_keys(T, 1.4, phase=0.4)},
        "hairL1": {"rotate": rotate_keys(T, 0.9, phase=-0.6)},
        "hairL2": {"rotate": rotate_keys(T, 1.6, phase=-0.9)},
        "hairL3": {"rotate": rotate_keys(T, 2.2, phase=-1.2)},
        "hairR1": {"rotate": rotate_keys(T, 0.9, phase=0.6)},
        "hairR2": {"rotate": rotate_keys(T, 1.6, phase=0.9)},
        "hairR3": {"rotate": rotate_keys(T, 2.2, phase=1.2)},
        "ahoge1": {"rotate": rotate_keys(T, 3.0, phase=0.8)},
        "ahoge2": {"rotate": rotate_keys(T, 4.0, phase=1.1)},
        "finL": {"rotate": rotate_keys(T, 2.2, phase=0.2)},
        "finR": {"rotate": rotate_keys(T, -2.2, phase=0.2)},
        "tail1": {"rotate": rotate_keys(T, 2.4)},
        "tail2": {"rotate": rotate_keys(T, 3.2, phase=-0.5)},
        "tailFin": {"rotate": rotate_keys(T, 4.5, phase=-1.0)},
        "skirt": {"rotate": rotate_keys(T, 0.6)},
        "eyeL": {"scale": blink_keys(T, 2.3)},
        "eyeR": {"scale": blink_keys(T, 2.3)},
    }}

    # ---- working: 2.2 s, busier tail and hair
    T = 2.2
    anims["working"] = {"bones": {
        "root": {"translate": translate_keys(T, 0.0, 1.8)},
        "spine": {"rotate": rotate_keys(T, 1.2, base=1.5)},
        "chest": {"scale": scale_keys(T, 0.010, 0.014)},
        "head": {"translate": translate_keys(T, 0.0, -1.6, base_y=-2.0),
                 "rotate": rotate_keys(T, 1.2, phase=0.5)},
        "hairL1": {"rotate": rotate_keys(T, 1.4, phase=-0.5)},
        "hairL2": {"rotate": rotate_keys(T, 2.4, phase=-0.8)},
        "hairL3": {"rotate": rotate_keys(T, 3.4, phase=-1.1)},
        "hairR1": {"rotate": rotate_keys(T, 1.4, phase=0.5)},
        "hairR2": {"rotate": rotate_keys(T, 2.4, phase=0.8)},
        "hairR3": {"rotate": rotate_keys(T, 3.4, phase=1.1)},
        "ahoge1": {"rotate": rotate_keys(T, 4.0, phase=0.3)},
        "ahoge2": {"rotate": rotate_keys(T, 5.5, phase=0.7)},
        "finL": {"rotate": rotate_keys(T, 3.0)},
        "finR": {"rotate": rotate_keys(T, -3.0)},
        "tail1": {"rotate": rotate_keys(T, 5.0)},
        "tail2": {"rotate": rotate_keys(T, 7.0, phase=-0.6)},
        "tailFin": {"rotate": rotate_keys(T, 9.0, phase=-1.2)},
        "skirt": {"rotate": rotate_keys(T, 1.0)},
        "eyeL": {"scale": blink_keys(T, 1.2)},
        "eyeR": {"scale": blink_keys(T, 1.2)},
    }}

    # ---- needs_input: 3 s inquiring tilt, ears up
    T = 3.0
    head_rot = [
        {"time": 0.0, "value": 0.0},
        {"time": 0.45, "value": 6.0},
        {"time": 2.35, "value": 6.0},
        {"time": 2.85, "value": 0.0},
        {"time": 3.0, "value": 0.0},
    ]
    head_tr = [
        {"time": 0.0, "x": 0.0, "y": 0.0},
        {"time": 0.45, "x": 0.0, "y": 2.5},
        {"time": 2.35, "x": 0.0, "y": 2.5},
        {"time": 2.85, "x": 0.0, "y": 0.0},
        {"time": 3.0, "x": 0.0, "y": 0.0},
    ]
    anims["needs_input"] = {"bones": {
        "root": {"translate": translate_keys(T, 0.0, 1.4)},
        "spine": {"rotate": rotate_keys(T, 0.8, base=0.6)},
        "neck": {"rotate": rotate_keys(T, 0.8, base=1.5)},
        "head": {"rotate": head_rot, "translate": head_tr},
        "hairL1": {"rotate": rotate_keys(T, 1.2)},
        "hairL2": {"rotate": rotate_keys(T, 2.0)},
        "hairL3": {"rotate": rotate_keys(T, 2.8)},
        "hairR1": {"rotate": rotate_keys(T, -1.2)},
        "hairR2": {"rotate": rotate_keys(T, -2.0)},
        "hairR3": {"rotate": rotate_keys(T, -2.8)},
        "ahoge1": {"rotate": rotate_keys(T, 4.5, phase=0.5)},
        "ahoge2": {"rotate": rotate_keys(T, 6.0, phase=0.9)},
        "finL": {"rotate": rotate_keys(T, -3.5, base=-5.0)},
        "finR": {"rotate": rotate_keys(T, 3.5, base=5.0)},
        "tail1": {"rotate": rotate_keys(T, 2.0, base=2.0)},
        "tail2": {"rotate": rotate_keys(T, 3.0, phase=-0.5, base=3.0)},
        "tailFin": {"rotate": rotate_keys(T, 4.0, phase=-1.0, base=7.0)},
        "skirt": {"rotate": rotate_keys(T, 0.5)},
    }}

    # ---- done: 1.4 s happy hop (played once)
    T = 1.4
    anims["done"] = {"bones": {
        "root": {
            "translate": [
                {"time": 0.0, "x": 0.0, "y": 0.0},
                {"time": 0.18, "x": 0.0, "y": 16.0},
                {"time": 0.36, "x": 0.0, "y": 0.0},
                {"time": 0.54, "x": 0.0, "y": 8.0},
                {"time": 0.72, "x": 0.0, "y": 0.0},
                {"time": 1.4, "x": 0.0, "y": 0.0},
            ],
            "scale": [
                {"time": 0.0, "x": 1.0, "y": 1.0},
                {"time": 0.10, "x": 0.97, "y": 1.05},
                {"time": 0.18, "x": 1.02, "y": 0.98},
                {"time": 0.36, "x": 0.98, "y": 1.04},
                {"time": 0.54, "x": 1.01, "y": 0.99},
                {"time": 0.72, "x": 1.0, "y": 1.0},
                {"time": 1.4, "x": 1.0, "y": 1.0},
            ],
        },
        "head": {"rotate": [
            {"time": 0.0, "value": 0.0},
            {"time": 0.18, "value": -4.0},
            {"time": 0.36, "value": 0.0},
            {"time": 0.54, "value": 4.0},
            {"time": 0.72, "value": 0.0},
            {"time": 1.4, "value": 0.0},
        ]},
        "hairL1": {"rotate": rotate_keys(T, 2.0, phase=-0.5)},
        "hairL2": {"rotate": rotate_keys(T, 3.0, phase=-0.9)},
        "hairL3": {"rotate": rotate_keys(T, 4.0, phase=-1.3)},
        "hairR1": {"rotate": rotate_keys(T, 2.0, phase=0.5)},
        "hairR2": {"rotate": rotate_keys(T, 3.0, phase=0.9)},
        "hairR3": {"rotate": rotate_keys(T, 4.0, phase=1.3)},
        "ahoge1": {"rotate": rotate_keys(T, 7.0, phase=0.6)},
        "ahoge2": {"rotate": rotate_keys(T, 9.0, phase=1.0)},
        "finL": {"rotate": rotate_keys(T, 5.0)},
        "finR": {"rotate": rotate_keys(T, -5.0)},
        "tail1": {"rotate": rotate_keys(T, 6.0)},
        "tail2": {"rotate": rotate_keys(T, 8.0, phase=-0.7)},
        "tailFin": {"rotate": rotate_keys(T, 10.0, phase=-1.4)},
        "skirt": {"rotate": rotate_keys(T, 1.2)},
    }}

    # ---- drink: 3.2 s loop, two sips (head dips, eyes close on the way up)
    T = 3.2
    anims["drink"] = {"bones": {
        "root": {"translate": xy_keys([
            (0.0, 0.0, 0.0), (0.6, 0.0, 1.2), (1.2, 0.0, 0.0),
            (2.0, 0.0, 1.2), (2.6, 0.0, 0.0), (T, 0.0, 0.0),
        ])},
        "chest": {"scale": scale_keys(T, 0.004, 0.010)},
        "spine": {"rotate": rotate_keys(T, 0.4)},
        "neck": {"rotate": scalar_keys([
            (0.0, 0.0), (0.75, 2.0), (1.15, 2.0), (1.45, 0.0),
            (2.35, 2.0), (2.75, 2.0), (3.0, 0.0), (T, 0.0),
        ])},
        "head": {
            "translate": xy_keys([
                (0.0, 0.0, 0.0), (0.45, 0.0, 0.0), (0.75, 0.0, -11.0),
                (1.15, 0.0, -11.0), (1.45, 0.0, 0.0), (2.05, 0.0, 0.0),
                (2.35, 0.0, -10.0), (2.75, 0.0, -10.0), (3.0, 0.0, 0.0),
                (T, 0.0, 0.0),
            ]),
            "rotate": scalar_keys([
                (0.0, 0.0), (0.75, 4.0), (1.15, 4.0), (1.45, 0.0),
                (2.35, 4.0), (2.75, 4.0), (3.0, 0.0), (T, 0.0),
            ]),
        },
        "hairL1": {"rotate": rotate_keys(T, 0.8, phase=-0.5)},
        "hairL2": {"rotate": rotate_keys(T, 1.4, phase=-0.8)},
        "hairL3": {"rotate": rotate_keys(T, 2.0, phase=-1.1)},
        "hairR1": {"rotate": rotate_keys(T, 0.8, phase=0.5)},
        "hairR2": {"rotate": rotate_keys(T, 1.4, phase=0.8)},
        "hairR3": {"rotate": rotate_keys(T, 2.0, phase=1.1)},
        "ahoge1": {"rotate": rotate_keys(T, 2.5, phase=0.8)},
        "ahoge2": {"rotate": rotate_keys(T, 3.5, phase=1.1)},
        "finL": {"rotate": scalar_keys([
            (0.0, 0.0), (0.9, -2.5), (1.5, 0.0), (2.4, -2.5), (3.0, 0.0), (T, 0.0),
        ])},
        "finR": {"rotate": scalar_keys([
            (0.0, 0.0), (0.9, 2.5), (1.5, 0.0), (2.4, 2.5), (3.0, 0.0), (T, 0.0),
        ])},
        "tail1": {"rotate": rotate_keys(T, 2.0)},
        "tail2": {"rotate": rotate_keys(T, 2.8, phase=-0.5)},
        "tailFin": {"rotate": rotate_keys(T, 3.8, phase=-1.0)},
        "skirt": {"rotate": rotate_keys(T, 0.5)},
        "eyeL": {"scale": multi_blink_keys(T, [1.5, 2.85])},
        "eyeR": {"scale": multi_blink_keys(T, [1.5, 2.85])},
    }}

    # ---- stretch: 2.8 s loop, rise on tiptoe, fins out, eyes shut
    T = 2.8
    anims["stretch"] = {"bones": {
        "root": {
            "translate": xy_keys([
                (0.0, 0.0, 0.0), (0.45, 0.0, 3.0), (0.95, 0.0, 8.0),
                (1.75, 0.0, 8.0), (2.2, 0.0, 0.0), (T, 0.0, 0.0),
            ]),
            "scale": xy_keys([
                (0.0, 1.0, 1.0), (0.5, 0.995, 1.02), (0.95, 0.98, 1.05),
                (1.75, 0.98, 1.05), (2.2, 1.0, 1.0), (T, 1.0, 1.0),
            ]),
        },
        "spine": {"rotate": scalar_keys([
            (0.0, 0.0), (0.9, -2.0), (1.75, -2.0), (2.2, 0.0), (T, 0.0),
        ])},
        "neck": {"rotate": scalar_keys([
            (0.0, 0.0), (0.9, -3.0), (1.75, -3.0), (2.2, 0.0), (T, 0.0),
        ])},
        "head": {"rotate": scalar_keys([
            (0.0, 0.0), (0.9, -5.0), (1.75, -5.0), (2.2, 0.0), (T, 0.0),
        ])},
        "hairL1": {"rotate": rotate_keys(T, 1.0, phase=-0.4)},
        "hairL2": {"rotate": rotate_keys(T, 1.8, phase=-0.7)},
        "hairL3": {"rotate": rotate_keys(T, 2.6, phase=-1.0)},
        "hairR1": {"rotate": rotate_keys(T, 1.0, phase=0.4)},
        "hairR2": {"rotate": rotate_keys(T, 1.8, phase=0.7)},
        "hairR3": {"rotate": rotate_keys(T, 2.6, phase=1.0)},
        "ahoge1": {"rotate": rotate_keys(T, 5.0, phase=0.5)},
        "ahoge2": {"rotate": rotate_keys(T, 7.0, phase=0.9)},
        "finL": {"rotate": scalar_keys([
            (0.0, 0.0), (0.9, -9.0), (1.75, -9.0), (2.2, 0.0), (T, 0.0),
        ])},
        "finR": {"rotate": scalar_keys([
            (0.0, 0.0), (0.9, 9.0), (1.75, 9.0), (2.2, 0.0), (T, 0.0),
        ])},
        "tail1": {"rotate": rotate_keys(T, 2.5, base=1.5)},
        "tail2": {"rotate": rotate_keys(T, 3.5, phase=-0.5, base=2.0)},
        "tailFin": {"rotate": rotate_keys(T, 5.0, phase=-1.0, base=3.0)},
        "skirt": {"rotate": rotate_keys(T, 0.8)},
        "eyeL": {"scale": xy_keys([
            (0.0, 1.0, 1.0), (0.85, 1.0, 1.0), (1.0, 1.0, 0.08),
            (1.65, 1.0, 0.08), (1.8, 1.0, 1.0), (T, 1.0, 1.0),
        ])},
        "eyeR": {"scale": xy_keys([
            (0.0, 1.0, 1.0), (0.85, 1.0, 1.0), (1.0, 1.0, 0.08),
            (1.65, 1.0, 0.08), (1.8, 1.0, 1.0), (T, 1.0, 1.0),
        ])},
    }}

    # ---- slack: 6 s lazy loop, half-lidded eyes, slow drift
    T = 6.0
    anims["slack"] = {"bones": {
        "root": {"translate": translate_keys(T, 2.0, 3.0)},
        "spine": {"rotate": rotate_keys(T, 0.7, base=1.0)},
        "chest": {"scale": scale_keys(T, 0.004, 0.007)},
        "neck": {"rotate": rotate_keys(T, 0.6, base=0.8)},
        "head": {"rotate": rotate_keys(T, 1.2, phase=0.3, base=1.5)},
        "hairL1": {"rotate": rotate_keys(T, 0.7, phase=-0.5)},
        "hairL2": {"rotate": rotate_keys(T, 1.2, phase=-0.8)},
        "hairL3": {"rotate": rotate_keys(T, 1.7, phase=-1.1)},
        "hairR1": {"rotate": rotate_keys(T, 0.7, phase=0.5)},
        "hairR2": {"rotate": rotate_keys(T, 1.2, phase=0.8)},
        "hairR3": {"rotate": rotate_keys(T, 1.7, phase=1.1)},
        "ahoge1": {"rotate": rotate_keys(T, 1.8, phase=0.7)},
        "ahoge2": {"rotate": rotate_keys(T, 2.4, phase=1.0)},
        "finL": {"rotate": rotate_keys(T, 1.2, base=-1.0)},
        "finR": {"rotate": rotate_keys(T, 1.2, phase=0.4, base=1.0)},
        "tail1": {"rotate": rotate_keys(T, 2.0, base=1.0)},
        "tail2": {"rotate": rotate_keys(T, 2.6, phase=-0.5, base=1.5)},
        "tailFin": {"rotate": rotate_keys(T, 3.4, phase=-1.0, base=2.5)},
        "skirt": {"rotate": rotate_keys(T, 0.4)},
        "eyeL": {"scale": xy_keys([
            (0.0, 1.0, 0.8), (1.2, 1.0, 0.45), (4.4, 1.0, 0.45),
            (5.2, 1.0, 0.75), (T, 1.0, 0.8),
        ])},
        "eyeR": {"scale": xy_keys([
            (0.0, 1.0, 0.8), (1.2, 1.0, 0.45), (4.4, 1.0, 0.45),
            (5.2, 1.0, 0.75), (T, 1.0, 0.8),
        ])},
    }}

    # ---- cheer: 1.6 s double hop, used for alarms and memos
    T = 1.6
    anims["cheer"] = {"bones": {
        "root": {
            "translate": xy_keys([
                (0.0, 0.0, 0.0), (0.12, 0.0, 14.0), (0.30, 0.0, 0.0),
                (0.46, 0.0, 10.0), (0.66, 0.0, 0.0), (T, 0.0, 0.0),
            ]),
            "scale": xy_keys([
                (0.0, 1.0, 1.0), (0.10, 0.96, 1.06), (0.20, 1.02, 0.98),
                (0.30, 1.0, 1.0), (0.42, 0.97, 1.05), (0.60, 1.0, 1.0),
                (T, 1.0, 1.0),
            ]),
        },
        "chest": {"scale": scale_keys(T, 0.012, 0.016)},
        "head": {"rotate": scalar_keys([
            (0.0, 0.0), (0.28, -5.0), (0.42, 5.0), (0.58, -4.0),
            (0.74, 4.0), (0.90, 0.0), (T, 0.0),
        ])},
        "hairL1": {"rotate": rotate_keys(T, 2.5, phase=-0.5)},
        "hairL2": {"rotate": rotate_keys(T, 3.6, phase=-0.8)},
        "hairL3": {"rotate": rotate_keys(T, 4.8, phase=-1.1)},
        "hairR1": {"rotate": rotate_keys(T, 2.5, phase=0.5)},
        "hairR2": {"rotate": rotate_keys(T, 3.6, phase=0.8)},
        "hairR3": {"rotate": rotate_keys(T, 4.8, phase=1.1)},
        "ahoge1": {"rotate": rotate_keys(T, 8.0, phase=0.6)},
        "ahoge2": {"rotate": rotate_keys(T, 11.0, phase=1.0)},
        "finL": {"rotate": rotate_keys(T, 9.0, base=-6.0)},
        "finR": {"rotate": rotate_keys(T, 9.0, phase=math.pi, base=6.0)},
        "tail1": {"rotate": rotate_keys(T, 8.0)},
        "tail2": {"rotate": rotate_keys(T, 12.0, phase=-0.6)},
        "tailFin": {"rotate": rotate_keys(T, 16.0, phase=-1.2)},
        "skirt": {"rotate": rotate_keys(T, 1.6)},
        "eyeL": {"scale": blink_keys(T, 0.75)},
        "eyeR": {"scale": blink_keys(T, 0.75)},
    }}
    return anims


# ---------------------------------------------------------------- output


def mirror_y(skel: dict) -> None:
    """Spine authors y-up; spine-godot renders a y-down skeleton.  Mirroring
    the whole skeleton once (bones, mesh binds, animation channels) makes the
    imported rig stand upright with a plain positive node scale."""
    for bone in skel["bones"]:
        if "y" in bone:
            bone["y"] = -bone["y"]
        if "rotation" in bone:
            bone["rotation"] = -bone["rotation"]
    for skin in skel["skins"]:
        for slot_atts in skin["attachments"].values():
            for att in slot_atts.values():
                verts = att.get("vertices")
                if not verts:
                    continue
                i = 0
                while i < len(verts):
                    n = verts[i]
                    i += 1
                    for _ in range(n):
                        verts[i + 2] = -verts[i + 2]
                        i += 4
    for timeline in skel["animations"].values():
        for channels in timeline["bones"].values():
            for key in channels.get("translate", []):
                key["y"] = -key["y"]
            for key in channels.get("rotate", []):
                key["value"] = -key["value"]


def write_atlas(path: str, page_name: str, page_size, regions):
    pw, ph = page_size
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(page_name + "\n")
        fh.write("size: %d,%d\n" % (pw, ph))
        fh.write("format: RGBA8888\n")
        fh.write("filter: Linear,Linear\n")
        fh.write("repeat: none\n")
        for name, (x, y), (w, h) in regions:
            fh.write(name + "\n")
            fh.write("  rotate: false\n")
            fh.write("  xy: %d, %d\n" % (x, y))
            fh.write("  size: %d, %d\n" % (w, h))
            fh.write("  orig: %d, %d\n" % (w, h))
            fh.write("  offset: 0, 0\n")
            fh.write("  index: -1\n")


def write_debug_weights(art, path, body_verts, body_uvs, xs, ys, cols, rows):
    body = art["body"]
    vis = Image.new("RGBA", body.size, (238, 238, 244, 255))
    vis.alpha_composite(body)
    d = ImageDraw.Draw(vis)
    palette = {
        "head": (230, 70, 70), "neck": (240, 140, 60), "chest": (230, 200, 50),
        "spine": (80, 190, 80), "hip": (60, 170, 170), "skirt": (80, 120, 230),
        "root": (130, 90, 200), "hairL1": (255, 100, 180), "hairL2": (200, 80, 220),
        "hairL3": (150, 60, 200), "hairR1": (255, 130, 130), "hairR2": (220, 100, 100),
        "hairR3": (180, 80, 80), "ahoge1": (255, 160, 40), "ahoge2": (255, 200, 80),
        "finL": (40, 200, 220), "finR": (40, 160, 200), "eyeL": (20, 20, 255),
        "eyeR": (80, 80, 255), "tail1": (0, 160, 0), "tail2": (0, 200, 0), "tailFin": (0, 240, 0),
    }
    inv = {v: k for k, v in BONE_INDEX.items()}
    for idx, entry in enumerate(body_verts):
        cx, cy = xs[idx % cols], ys[idx // cols]
        if idx % 2:
            continue
        best = max(entry, key=lambda e: e[3])
        color = palette.get(inv.get(best[0], "root"), (0, 0, 0))
        d.ellipse((cx - 1, cy - 1, cx + 1, cy + 1), fill=color)
    for name, _p, x, y in BONES:
        px = x + SRC_CX - art["crop_box"][0]
        py = SRC_BOTTOM - y - art["crop_box"][1]
        if not (0 <= px < body.width and 0 <= py < body.height):
            continue
        d.ellipse((px - 3, py - 3, px + 3, py + 3), outline=(0, 0, 0), width=1)
        d.text((px + 4, py - 6), name, fill=(0, 0, 0))
    vis.convert("RGB").save(path)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="assets/art/pet_portrait.png")
    ap.add_argument("--out", default="game/assets/pet_spine")
    ap.add_argument("--debug", default="tools/_debug")
    args = ap.parse_args()

    src = Image.open(args.src)
    art = prepare_art(src, args.debug)
    body = art["body"]
    cb = art["crop_box"]

    uvs, tris, flat, verts, xs, ys, cols, rows = build_mesh(
        cb, lambda x, y: body_vertex_weights(x, y, art))

    os.makedirs(args.out, exist_ok=True)

    # atlas page: one region, the body (which includes the tail)
    page_w = 1 << math.ceil(math.log2(body.width))
    page_h = 1 << math.ceil(math.log2(body.height))
    page = Image.new("RGBA", (page_w, page_h), (0, 0, 0, 0))
    page.alpha_composite(body, (0, 0))
    page.save(os.path.join(args.out, "pet.png"))

    write_atlas(os.path.join(args.out, "pet.atlas"), "pet.png",
                (page_w, page_h), [("body", (0, 0), body.size)])

    # skeleton JSON
    bone_json = []
    for name, parent, x, y in BONES:
        if parent is None:
            lx, ly = x, y
        else:
            px, py = BONE_WORLD[parent]
            lx, ly = x - px, y - py
        bone = {"name": name, "x": round(lx, 3), "y": round(ly, 3)}
        if parent:
            bone["parent"] = parent
        bone_json.append(bone)

    def mesh_json(uvs, tris, flat, size):
        return {
            "type": "mesh",
            "uvs": [round(v, 6) for v in uvs],
            "triangles": tris,
            "vertices": flat,
            "width": size[0],
            "height": size[1],
        }

    skel = {
        "skeleton": {
            "spine": "4.2.43",
            "x": 0.0,
            "y": 0.0,
            "width": body.width,
            "height": body.height,
            "images": "./",
            "audio": "",
        },
        "bones": bone_json,
        "slots": [
            {"name": "body", "bone": "root", "attachment": "body"},
        ],
        "skins": [{
            "name": "default",
            "attachments": {
                "body": {"body": mesh_json(uvs, tris, flat, body.size)},
            },
        }],
        "animations": build_animations(),
    }
    mirror_y(skel)
    with open(os.path.join(args.out, "pet.spine-json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(skel, fh, ensure_ascii=False, separators=(",", ":"))

    if args.debug:
        os.makedirs(args.debug, exist_ok=True)
        write_debug_weights(art, os.path.join(args.debug, "weights.png"),
                            verts, uvs, xs, ys, cols, rows)

    print("body %dx%d  verts %d  tris %d" % (
        body.width, body.height, len(verts), len(tris) // 3))
    print("json bytes:", os.path.getsize(os.path.join(args.out, "pet.spine-json")))


if __name__ == "__main__":
    main()
