#!/usr/bin/env python3
"""Build the layered Spine rig for the 「大肥鱼」 desktop pet.

Splits assets/art/pet_portrait.png into independently animated layers
(body, head, long hair x2, tail, skirt/apron, upper/fore arms, hands,
face patches, cup, grip hand), packs them into one atlas, and writes the
skeleton JSON with the 250 ml drink sample:

    drink_in  ->  drink_sip x N  ->  drink_out

Outputs (game/assets/pet_spine/):
    pet.png             packed atlas
    pet.atlas           region table
    pet.spine-json      skeleton + animations
    pet_silhouette.png  alpha silhouette for hit testing (599x820)

Run from the project root:
    python tools/build_spine.py
"""
import argparse
import json
import math
import os
from collections import deque

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from deepseek_whale import render_whale, render_whale_parts
from hand_cut import HANDS as HAND_PLACEMENTS, cut_all as cut_hands, place_hand

SRC_CX = 470.0          # character centre line in the source image
SRC_TOP = 132.0         # top of the character; the skeleton's y = 0 line
# spine-godot renders skeleton space (y-up) into Godot space (y-down) by
# negating y, so the raw JSON must be y-up: a vertex at source row y gets
# skeleton y = SRC_TOP - y, which lands at rendered y = y - SRC_TOP.
SRC_BOTTOM = 952.0      # sole of the feet in the source image
HEAD_CUT = 545          # rows <= this belong to the head layer
PAD = 2                 # transparent padding around every packed region
GUTTER = 2              # gap between regions in the atlas

GRID_BODY = 8.0
GRID_HAIR = 8.0
GRID_TAIL = 8.0
GRID_ARM = 5.0

# ---------------------------------------------------------------- polygons

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

LHAIR = [
    (340, 400), (315, 406), (292, 418), (270, 434), (250, 454), (232, 478),
    (216, 504), (202, 532), (191, 562), (184, 592), (181, 622), (183, 652),
    (189, 682), (198, 708), (212, 730), (232, 746), (255, 756), (278, 758),
    (298, 752), (312, 740), (320, 724), (318, 708), (310, 692), (306, 680),
    (308, 664), (316, 652), (334, 640), (348, 620), (356, 600), (374, 580),
    (380, 560), (384, 544), (380, 526), (372, 508), (364, 490), (360, 472),
    (362, 454), (368, 436), (376, 420), (384, 410), (360, 398),
]

RHAIR = [
    (600, 400), (625, 406), (648, 418), (670, 434), (690, 454), (708, 478),
    (724, 504), (738, 532), (749, 562), (756, 592), (759, 622), (757, 652),
    (751, 682), (742, 708), (728, 730), (708, 746), (685, 756), (662, 758),
    (642, 752), (628, 740), (620, 724), (622, 708), (632, 692), (638, 676),
    (642, 660), (640, 644), (628, 628), (616, 612), (606, 596), (600, 580),
    (598, 564), (598, 548), (604, 530), (612, 512), (618, 494), (620, 476),
    (616, 458), (608, 440), (600, 422), (596, 406),
]

SKIRT = [
    (352, 640), (340, 665), (325, 695), (310, 725), (300, 755), (295, 780),
    (300, 800), (318, 815), (350, 825), (390, 830), (440, 833), (500, 833),
    (555, 830), (600, 822), (635, 810), (655, 792), (662, 770), (658, 745),
    (646, 715), (632, 685), (618, 658), (600, 640), (575, 632), (540, 628),
    (500, 627), (460, 628), (420, 632), (385, 636),
]

APRON = [
    (388, 586), (400, 576), (430, 572), (470, 572), (520, 572), (560, 576),
    (580, 590), (590, 615), (598, 645), (602, 675), (600, 705), (590, 730),
    (575, 748), (550, 760), (520, 766), (490, 768), (460, 766), (430, 760),
    (405, 748), (390, 730), (382, 705), (380, 678), (382, 650), (385, 620),
]

HAND_L = [
    (300, 680), (310, 674), (325, 671), (342, 675), (352, 683), (354, 694),
    (347, 704), (335, 710), (319, 709), (306, 701), (300, 690),
]
HAND_R = [
    (594, 680), (604, 674), (619, 671), (636, 675), (646, 683), (648, 694),
    (641, 704), (629, 710), (613, 709), (600, 701), (594, 690),
]

FACE_RECT = (338, 416, 602, 510)
EYE_BOX = {"L": (344, 420, 451, 506), "R": (489, 420, 596, 506)}
EYE_CTR = {"L": (405, 470), "R": (537, 470)}
MOUTH_RECT = (444, 488, 502, 524)

# ---------------------------------------------------------------- bones
# name, parent, source x, source y   (image pixels, y down)
BONES = [
    ("root", None, 470.0, 952.0),
    ("hip", "root", 470.0, 700.0),
    ("spine", "hip", 470.0, 640.0),
    ("chest", "spine", 470.0, 590.0),
    ("neck", "chest", 470.0, 552.0),
    ("head", "neck", 470.0, 538.0),
    ("hairL1", "head", 335.0, 475.0),
    ("hairL2", "hairL1", 300.0, 610.0),
    ("hairL3", "hairL2", 278.0, 745.0),
    ("hairR1", "head", 608.0, 475.0),
    ("hairR2", "hairR1", 640.0, 610.0),
    ("hairR3", "hairR2", 662.0, 745.0),
    ("tail1", "hip", 590.0, 790.0),
    ("tail2", "tail1", 675.0, 760.0),
    ("tailFin", "tail2", 730.0, 700.0),
    ("skirt", "hip", 470.0, 665.0),
    ("armL1", "chest", 414.0, 566.0),
    ("armL2", "armL1", 363.0, 625.0),
    ("handL", "armL2", 338.0, 663.0),
    ("armR1", "chest", 539.0, 566.0),
    ("armR2", "armR1", 577.0, 625.0),
    ("handR", "armR2", 607.0, 676.0),
    # the bottle is its own bone; both hands follow the grip targets on its
    # sides via IK, so the bottle never hangs off a single hand.  The grips sit
    # at the wrists: the grip-hand art is bound to THEM, not to the hand bones,
    # so the hands stay glued to the bottle while the forearms swing.
    ("cup", "chest", 470.0, 630.0),
    ("drink_lift", "chest", 580.0, 560.0),
    ("drink_prop", "drink_lift", 650.0, 420.0),
    ("d_armL1", "chest", 460.0, 552.0),
    ("d_armL2", "d_armL1", 548.0, 570.0),
    ("d_handL", "d_armL2", 602.0, 486.0),
    ("d_armR1", "chest", 615.0, 535.0),
    ("d_armR2", "d_armR1", 676.0, 550.0),
    ("d_handR", "d_armR2", 696.0, 484.0),
    ("d_gripL", "drink_prop", 602.0, 486.0),
    ("d_gripR", "drink_prop", 696.0, 484.0),
    ("work_prop", "chest", 470.0, 612.0),
    ("write_tip", "work_prop", 442.0, 583.0),
    ("gripL", "cup", 420.0, 620.0),
    ("gripR", "cup", 520.0, 620.0),
    # ---- side view (the drink).  These are the 3/4 painting's own joints:
    # its sleeves hang further out and lower than the front portrait's, so
    # binding them to the front elbow would swing them around the wrong pivot
    # and tear the shoulder.  The fists are painted into the forearm layer, so
    # each forearm bone ends at the FIST centre -- the IK tip is then the hand
    # that holds the glass, and the cuff rides along on the same bone.
    ("s_armL1", "chest", 420.0, 562.0),
    ("s_armL2", "s_armL1", 411.0, 610.0),
    ("s_handL", "s_armL2", 367.0, 686.0),
    ("s_armR1", "chest", 572.0, 560.0),
    ("s_armR2", "s_armR1", 574.0, 611.0),
    ("s_handR", "s_armR2", 612.0, 681.0),
    # grip point for the side hold: the near hand takes the glass by the neck.
    # The far hand cannot join it -- her far shoulder is 201 px from the lips
    # and that arm is 137 px -- so it stays at her side, where the painting
    # already has it.  A separate bone from gripR keeps the front drink's
    # two-handed hold untouched.
    ("s_grip_r", "cup", 510.0, 590.0),
    # animated water level: scale.y shrinks it toward the bottle's base
    ("water", "cup", 470.0, 658.0),
    # props are independent bones so the hands can be driven onto them by IK
    ("book", "chest", 470.0, 612.0),
    ("pen", "book", 492.0, 570.0),
    ("fish", "chest", 470.0, 628.0),
    # IK wrist targets for the props (children of the prop = they follow it)
    ("workL", "book", 424.0, 610.0),
    ("workR", "pen", 541.0, 600.0),
    # wrists of the hugging hands: the art below is drawn around these,
    # so IK puts the cuff exactly on the hand and the palms stay on
    # the fish instead of floating beside it.
    # The left palm goes UNDER the whale (cradle); the right one sits on its
    # BACK, clear of the eye and mouth, which the old side position covered.
    # The support target is near full reach. The stroking target must remain
    # well outside the chain's minimum reach so the elbow cannot fold back
    # through the hand during a sideways stroke.
    ("slackL", "fish", 375.0, 706.0),
    ("slackR", "fish", 470.0, 607.0),
]

# Two-bone IK keeps each hand glued to the cup's side: the forearm tip (where
# the hand bone attaches) reaches the grip bone, which rides on the cup.
# mix 0 at setup -> arms stay FK everywhere except the drink clips, which key it
# up to 1.
# spine-cpp's JSON reader (spine-godot 4.2) reads the bend as "bendPositive"
# (a boolean), NOT "bendDirection": getInt("bendPositive", 1) ? 1 : -1. The left
# elbow must swing outward (positive bend) and the right one the mirrored way.
IK = [
    # Each constraint needs a DISTINCT order: Skeleton::updateWorldTransform
    # walks order 0..N-1 and matches one constraint per index, so two IK
    # constraints sharing order 0 leaves the second one never sorted/applied.
    # Only one arm pair is active at a time (mix > 0); the others sit at mix 0.
    {"name": "ik_arm_l", "order": 0, "bones": ["armL1", "armL2"], "target": "gripL",
     "mix": 0.0, "softness": 0.0, "bendPositive": True, "compress": False,
     "stretch": False, "uniform": False},
    {"name": "ik_arm_r", "order": 1, "bones": ["armR1", "armR2"], "target": "gripR",
     "mix": 0.0, "softness": 0.0, "bendPositive": False, "compress": False,
     "stretch": False, "uniform": False},
    {"name": "ik_work_l", "order": 2, "bones": ["armL1", "armL2"], "target": "workL",
     "mix": 0.0, "softness": 0.0, "bendPositive": True, "compress": False,
     "stretch": False, "uniform": False},
    {"name": "ik_work_r", "order": 3, "bones": ["armR1", "armR2"], "target": "workR",
     "mix": 0.0, "softness": 0.0, "bendPositive": False, "compress": False,
     "stretch": False, "uniform": False},
    {"name": "ik_slack_l", "order": 4, "bones": ["armL1", "armL2"], "target": "slackL",
     "mix": 0.0, "softness": 0.0, "bendPositive": True, "compress": False,
     "stretch": False, "uniform": False},
    {"name": "ik_slack_r", "order": 5, "bones": ["armR1", "armR2"], "target": "slackR",
     "mix": 0.0, "softness": 0.0, "bendPositive": False, "compress": False,
     "stretch": False, "uniform": False},
    {"name": "s_ik_arm_r", "order": 6, "bones": ["s_armR1", "s_armR2"],
     "target": "s_grip_r", "mix": 0.0, "softness": 0.0, "bendPositive": False,
     "compress": False, "stretch": False, "uniform": False},
    {"name": "d_ik_l", "order": 7, "bones": ["d_armL1", "d_armL2"],
     "target": "d_gripL", "mix": 0.0, "bendPositive": True},
    {"name": "d_ik_r", "order": 8, "bones": ["d_armR1", "d_armR2"],
     "target": "d_gripR", "mix": 0.0, "bendPositive": True},
]
BONE_WORLD = {name: (x - SRC_CX, SRC_TOP - y) for name, _p, x, y in BONES}
BONE_INDEX = {name: i for i, (name, _p, _x, _y) in enumerate(BONES)}


# ------------------------------------------------------- forearm aim
# The two-bone IK solver measures its reach along the child bone's local +x: the
# "tip" is the forearm origin plus BoneData.length along that axis.  In this
# position-only rig the wrist sat off that axis, so the IK drove the tip onto the
# grip while the hand graphic stayed 80 px away.  Aim each forearm at its wrist
# once, in setup, and put the hand bone at (length, 0) in the forearm's frame so
# tip == wrist == grip target.
#
# Bone rotations in the JSON are authored in screen convention and negated by
# mirror_animations(), so store the negated angle.
def _aim_deg(parent, child):
    px, py = BONE_WORLD[parent]
    cx, cy = BONE_WORLD[child]
    return math.degrees(math.atan2(cy - py, cx - px))

ARM_AIM = {"armL2": _aim_deg("armL2", "handL"),
           "armR2": _aim_deg("armR2", "handR"),
           "s_armL2": _aim_deg("s_armL2", "s_handL"),
           "s_armR2": _aim_deg("s_armR2", "s_handR"),
           "d_armL2": _aim_deg("d_armL2", "d_handL"),
           "d_armR2": _aim_deg("d_armR2", "d_handR")}
# skeleton-space world rotation of every bone that carries a hand graphic
BONE_ROT_WORLD = {
    "d_armL2": ARM_AIM["d_armL2"], "d_handL": ARM_AIM["d_armL2"],
    "d_armR2": ARM_AIM["d_armR2"], "d_handR": ARM_AIM["d_armR2"],
    "armL2": ARM_AIM["armL2"], "handL": ARM_AIM["armL2"],
    "armR2": ARM_AIM["armR2"], "handR": ARM_AIM["armR2"],
    "s_armL2": ARM_AIM["s_armL2"], "s_handL": ARM_AIM["s_armL2"],
    "s_armR2": ARM_AIM["s_armR2"], "s_handR": ARM_AIM["s_armR2"],
}


def bone_offset(bone, wx, wy):
    """Vertex offset in `bone`'s local frame.  The bone transform applied to it
    at setup must land on world (wx, wy); a rotated bone therefore stores the
    delta rotated back by -R.  Bones without rotation keep the plain delta."""
    bx, by = BONE_WORLD[bone]
    dx, dy = wx - bx, wy - by
    r = BONE_ROT_WORLD.get(bone)
    if not r:
        return dx, dy
    c, s = math.cos(math.radians(r)), math.sin(math.radians(r))
    return c * dx + s * dy, -s * dx + c * dy

SLOTS = [
    # static hair behind the head: the body and skirt are cut around the hair,
    # so a head turn would otherwise open a hole onto the desktop
    ("hair_back", "root", "hair_back"),
    ("hair_l", "hairL1", "hair_l"),
    ("hair_r", "hairR1", "hair_r"),
    ("body", "root", "body"),
    ("skirt", "skirt", "skirt"),
    # the tail passes in front of the skirt in the art and behind the sleeves,
    # so it sits between the two
    ("tail", "tail1", "tail"),
    ("arm_up_l", "armL1", "arm_up_l"),
    ("arm_up_r", "armR1", "arm_up_r"),
    ("arm_fore_l", "armL2", "arm_fore_l"),
    ("arm_fore_r", "armR2", "arm_fore_r"),
    # props are hidden at setup and attached only by their clips.  The book
    # and fish sit under the hands; the pen is drawn over the writing hand.
    ("book", "book", ""),
    ("book_hand", "workL", ""),
    ("fish", "fish", ""),
    ("hand_l", "handL", "hand_l"),
    ("hand_r", "handR", "hand_rest"),
    ("pen", "pen", ""),
    # the fist on the pen rides the pen bone, so it writes with the nib
    ("pen_hand", "pen", ""),
    ("head", "head", "head"),
    ("eyes", "head", "eyes_open"),
    ("mouth", "head", "mouth_default"),
    # ---- side set for the drink: the 3/4 body with the head-up face swapped
    # in.  Hidden at setup; the drink clips fade the front set out and this one
    # in, so only the face and neck change and the skirt never jumps.
    # Draw order inside the set: body, then the head, then BOTH forearms -- the
    # hands hold the glass at the chin, so they belong in front of the neck --
    # with the far arm before the bottle and the near arm after it.
    ("s_hair_back", "root", ""),
    ("s_body", "root", ""),
    ("s_arm_up_l", "s_armL1", ""),
    ("s_arm_up_r", "s_armR1", ""),
    ("s_head", "head", ""),
    ("s_arm_fore_l", "s_armL2", ""),
    # water sits behind the glass; the bottle is glass in front of it
    ("water", "water", ""),
    ("cup", "cup", ""),
    # the grip hands ride on the bottle's grip bones, in front of everything
    ("cup_hand_l", "gripL", ""),
    ("cup_hand_r", "gripR", ""),
    # the near forearm grips the glass from the viewer's side, so it is drawn
    # over the bottle
    ("s_arm_fore_r", "s_armR2", ""),
    ("d_upper_l", "d_armL1", ""),
    ("d_upper_r", "d_armR1", ""),
    ("d_fore_l", "d_armL2", ""),
    ("d_fore_r", "d_armR2", ""),
    ("drink_arms", "drink_prop", ""),
    ("work_arms", "work_prop", ""),
    # the hugging hands ride on the fish's wrist bones (slackL/R), so
    # they cannot drift off it while the arms follow by IK
    ("fish_hand_l", "slackL", ""),
    ("fish_hand_r", "slackR", ""),
    # duplicate slots at the very front, on the same bones.  Presenting,
    # waving, cheering and stretching raise the arms past the side hair, and
    # the head layer (front hair) covers them; spine-godot's drawOrder timeline
    # does not reorder the render here, so anything that has to cross the head
    # needs its own slot after it.  Forearms sit under the palms.
    ("arm_up_l_front", "armL1", ""),
    ("arm_up_r_front", "armR1", ""),
    ("arm_fore_l_front", "armL2", ""),
    ("arm_fore_r_front", "armR2", ""),
    ("hand_l_front", "handL", ""),
    ("hand_r_front", "handR", ""),
    # ...and the hugging palms need their own pair, after the forearms, or the
    # sleeves that wrap the plush cover the very hands doing the holding.
    ("fish_hand_l_front", "slackL", ""),
    ("fish_hand_r_front", "slackR", ""),
]

GRIDS = {
    "body": GRID_BODY, "hair_l": GRID_HAIR, "hair_r": GRID_HAIR,
    "tail": GRID_TAIL, "skirt": GRID_HAIR,
    "arm_up_l": GRID_ARM, "arm_up_r": GRID_ARM,
    "arm_fore_l": GRID_ARM, "arm_fore_r": GRID_ARM,
}


def clamp01(v):
    return 0.0 if v < 0.0 else (1.0 if v > 1.0 else v)


def smoothstep(a, b, v):
    if a == b:
        return 1.0 if v >= b else 0.0
    t = clamp01((v - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def img_to_world(x, y):
    return (x - SRC_CX, SRC_TOP - y)


# ---------------------------------------------------------------- masks

def poly_mask(size, pts, grow=0):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).polygon(pts, fill=255)
    if grow:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    return m


def union(*ms):
    out = ms[0]
    for m in ms[1:]:
        out = ImageChops.lighter(out, m)
    return out


def invert(m):
    return m.point(lambda v: 255 - v)


def band_mask(size, y0, y1):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rectangle((0, y0, size[0], y1), fill=255)
    return m


def flood_mask(im, seed, pred):
    W, H = im.size
    m = Image.new("L", (W, H), 0)
    mp = m.load()
    p = im.load()
    sx, sy = seed
    if not pred(*p[sx, sy]):
        raise ValueError("flood seed %s failed: %s" % (seed, p[sx, sy]))
    q = deque([seed])
    mp[sx, sy] = 255
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and not mp[nx, ny] and pred(*p[nx, ny]):
                mp[nx, ny] = 255
                q.append((nx, ny))
    return m


def solid_rows(mask, grow=0):
    """Fill 1-px gaps between set pixels inside each scan row."""
    m = mask.copy()
    bb = m.getbbox()
    if not bb:
        return m
    x0, y0, x1, y1 = bb
    p = m.load()
    for y in range(y0, y1):
        xs = [x for x in range(x0, x1) if p[x, y]]
        if not xs:
            continue
        for x in range(min(xs), max(xs) + 1):
            p[x, y] = 255
    if grow:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    return m


def apply_mask(im, mask, dilate=0):
    m = mask.filter(ImageFilter.MaxFilter(dilate * 2 + 1)) if dilate else mask
    out = im.copy()
    out.putalpha(ImageChops.multiply(im.getchannel("A"), m))
    return out


def cut(im, mask):
    out = im.copy()
    out.putalpha(ImageChops.multiply(im.getchannel("A"), invert(mask)))
    return out


def is_hair(r, g, b, a):
    if a < 90:
        return False
    mx, mn = max(r, g, b), min(r, g, b)
    return b == mx and (mx - mn) > 34 and b > 120 and b > r * 1.02


def is_hair_dark(r, g, b, a):
    return a > 90 and b >= r and b >= g and b > 45 and (r + g + b) < 330


def is_blue(r, g, b, a):
    if a < 60:
        return False
    mx, mn = max(r, g, b), min(r, g, b)
    return b == mx and (mx - mn) > 18 and b > 70


def is_skin(r, g, b, a):
    return a > 170 and r > 210 and g > 150 and b > 140 and r >= g >= b - 4 and (r - b) > 10


def is_pale(r, g, b, a):
    return a > 180 and min(r, g, b) > 198 and max(r, g, b) - min(r, g, b) < 48


def is_outline(r, g, b, a):
    return a > 60 and (r + g + b) < 210


# ---------------------------------------------------------------- inpaint

def nearest_fill(im, target, source, max_dist=60, bright_only=False):
    out = im.copy()
    p = out.load()
    t = target.load()
    sm = source.load()
    sp = im.load()
    src = []
    for y in range(out.height):
        for x in range(out.width):
            if sm[x, y] and sp[x, y][3] > 0:
                if bright_only and sum(sp[x, y][:3]) < 210:
                    continue
                src.append((x, y))
    q = deque(src)
    seen = set(src)
    dist = {s: 0 for s in src}
    while q:
        x, y = q.popleft()
        d = dist[(x, y)]
        if d >= max_dist:
            continue
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if nx < 0 or ny < 0 or nx >= out.width or ny >= out.height or (nx, ny) in seen:
                continue
            if not t[nx, ny]:
                continue
            p[nx, ny] = p[x, y][:3] + (255,)
            seen.add((nx, ny))
            dist[(nx, ny)] = d + 1
            q.append((nx, ny))
    return out


def blur_fill(im, target, radius=24):
    """Fill wide holes with the tone of the art around them.

    ``nearest_fill`` copies one seed colour outward, so a hole wider than a
    few pixels comes out as onion rings / stair steps.  Here the layer is
    blurred across the hole several times and each pixel is taken from the
    alpha-weighted average, so only real artwork colour reaches the hole and
    the result is a smooth gradient instead of flat bands.
    """
    out = im.copy()
    p = out.load()
    t = target.load()
    W, H = out.size
    hole = []
    for y in range(H):
        for x in range(W):
            if t[x, y] and p[x, y][3] <= 8:
                hole.append((x, y))
    if not hole:
        return out
    # hair and fin are blue: keep the warm skin / white frill out of the field
    field = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    fp = field.load()
    any_seed = False
    for y in range(H):
        for x in range(W):
            c = p[x, y]
            # blue-dominant only: a plain b >= r also matches white lace and
            # greys the hole out where the cuff surrounds it
            if c[3] > 8 and c[2] - c[0] > 22:
                fp[x, y] = c
                any_seed = True
    if not any_seed:
        for y in range(H):
            for x in range(W):
                if p[x, y][3] > 8:
                    fp[x, y] = p[x, y]
    for r in (56, 40, 28, 18, 10, 5):
        bl = field.filter(ImageFilter.GaussianBlur(r)).load()
        for x, y in hole:
            a = bl[x, y][3]
            if a > 6:
                p[x, y] = (min(255, bl[x, y][0] * 255 // a),
                           min(255, bl[x, y][1] * 255 // a),
                           min(255, bl[x, y][2] * 255 // a), 255)
                fp[x, y] = p[x, y]
    return out


def mask_blur(im, mask, passes=2):
    """Box blur restricted to the mask, to melt the onion-peel stair edges."""
    out = im.copy()
    p = out.load()
    mp = mask.load()
    coords = [(x, y) for y in range(out.height) for x in range(out.width) if mp[x, y]]
    for _ in range(passes):
        tmp = out.copy()
        src = tmp.load()
        for x, y in coords:
            rs = gs = bs = n = 0
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= out.width or ny >= out.height:
                        continue
                    if not mp[nx, ny]:
                        continue
                    r, g, b, _a = src[nx, ny]
                    rs += r
                    gs += g
                    bs += b
                    n += 1
            if n:
                p[x, y] = (rs // n, gs // n, bs // n, 255)
    return out


def fill_vertical(im, mask, smooth=3, reach=400):
    """Fill each hole column from the body directly above and below it.

    A horizontal fill drags in whatever borders the hole on the inside, and
    beside the arm that is the white apron frill, so the navy shoulder turns
    into white stripes. Continuing the column keeps the dress navy on top and
    the skirt below, which is what the arm actually hides."""
    out = im.copy()
    p = out.load()
    mp = mask.load()
    W, H = out.size
    plan = []
    for x in range(W):
        y = 0
        while y < H:
            if not mp[x, y]:
                y += 1
                continue
            y0 = y
            while y < H and mp[x, y]:
                y += 1
            y1 = y
            up = down = None
            for yy in range(y0 - 1, max(-1, y0 - reach), -1):
                if p[x, yy][3] > 60:
                    up = (yy, p[x, yy])
                    break
            for yy in range(y1, min(H, y1 + reach)):
                if p[x, yy][3] > 60:
                    down = (yy, p[x, yy])
                    break
            if up is None and down is None:
                continue
            plan.append((x, y0, y1, up, down))
    # one stray gold trim or frill pixel above the hole would draw a bright
    # vertical line all the way down it, so take the median over a column band.
    # The band must stay on the same hole: a column can hold an arm hole and a
    # hem hole at once, and mixing their seeds pulled the white hem frill up
    # into the dress (the pale smudge at the right hip).
    for i, (x, y0, y1, up, down) in enumerate(plan):
        band = [e[3][1] for e in plan if e[3] is not None and abs(e[0] - x) <= 4
                and abs(e[1] - y0) <= 24]
        if up is not None and len(band) > 2:
            band.sort(key=lambda c: c[0] + c[1] + c[2])
            up = (up[0], band[len(band) // 2])
        band = [e[4][1] for e in plan if e[4] is not None and abs(e[0] - x) <= 4
                and abs(e[1] - y0) <= 24]
        if down is not None and len(band) > 2:
            band.sort(key=lambda c: c[0] + c[1] + c[2])
            down = (down[0], band[len(band) // 2])
        plan[i] = (x, y0, y1, up, down)
    for x, y0, y1, up, down in plan:
        if up is not None and down is not None:
            ya, ca = up
            yb, cb = down
            span = float(max(1, yb - ya))
            for yy in range(y0, y1):
                t = (yy - ya) / span
                p[x, yy] = (int(ca[0] + (cb[0] - ca[0]) * t),
                            int(ca[1] + (cb[1] - ca[1]) * t),
                            int(ca[2] + (cb[2] - ca[2]) * t), 255)
        else:
            c = (up or down)[1]
            for yy in range(y0, y1):
                p[x, yy] = (c[0], c[1], c[2], 255)
    return mask_blur(out, mask, smooth)


def fill_enclosed(im, mask, smooth=3):
    """Fill holes only where the layer has artwork on both sides of the row.

    The arms are cut out of the body and skirt layers, so raising an arm
    uncovers whatever was behind it.  Inside the garment silhouette that has
    to be the garment; along the outer edge the arm *was* the silhouette, and
    inventing cloth there would leave an empty sleeve behind.  So: paint the
    hole from its left/right neighbours only while both exist.
    """
    out = im.copy()
    p = out.load()
    mp = mask.load()
    W, H = out.size
    for y in range(H):
        xs = [x for x in range(W) if p[x, y][3] > 8]
        if not xs:
            continue
        first, last = xs[0], xs[-1]
        x = first + 1
        while x < last:
            if not mp[x, y] or p[x, y][3] > 8:
                x += 1
                continue
            x0 = x
            while x < last and mp[x, y] and p[x, y][3] <= 8:
                x += 1
            x1 = x - 1
            left = p[x0 - 1, y]
            right = p[x1 + 1, y]
            span = float(max(1, x1 - x0 + 1))
            for xx in range(x0, x1 + 1):
                t = (xx - x0 + 0.5) / span
                p[xx, y] = (int(left[0] + (right[0] - left[0]) * t),
                            int(left[1] + (right[1] - left[1]) * t),
                            int(left[2] + (right[2] - left[2]) * t), 255)
    return mask_blur(out, mask, smooth)


def inpaint_holes(im, mask, smooth=2):
    """Grow the surrounding colour into the hole one layer at a time.

    Useful when the hole is enclosed and its boundary is uniform; on a hole
    shaped like the whole arm it smears the wrist and apron colours into an
    arm-shaped ghost, so the torso fills use fill_vertical instead."""
    out = im.copy()
    p = out.load()
    mp = mask.load()
    hole = set()
    for y in range(out.height):
        for x in range(out.width):
            if mp[x, y]:
                hole.add((x, y))
    if not hole:
        return out
    ring = 0
    while hole and ring < 400:
        ring += 1
        frontier = {}
        for x, y in hole:
            rs = gs = bs = n = 0
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx == 0 and dy == 0:
                        continue
                    nx, ny = x + dx, y + dy
                    if nx < 0 or ny < 0 or nx >= out.width or ny >= out.height:
                        continue
                    if (nx, ny) in hole:
                        continue
                    r, g, b, a = p[nx, ny]
                    if a < 40:
                        continue
                    rs += r
                    gs += g
                    bs += b
                    n += 1
            if n:
                frontier[(x, y)] = (rs // n, gs // n, bs // n, 255)
        if not frontier:
            break
        for xy, c in frontier.items():
            p[xy[0], xy[1]] = c
        for xy in frontier:
            hole.discard(xy)
    return mask_blur(out, mask, smooth)


# ---------------------------------------------------------------- layers

def build_masks(im, p, ap, W, H):
    mk = {}
    navy = (lambda r, g, b, a: a > 120 and max(r, g, b) >= 70 and b >= max(r, g, b)
            and max(r, g, b) < 175 and b > 70)
    mk["sleeve_L"] = solid_rows(flood_mask(im, (370, 600), navy), grow=1)
    mk["sleeve_R"] = solid_rows(flood_mask(im, (570, 600), navy), grow=1)

    # the white cuff frills are shading-heavy; bound them by their boxes and
    # pick up every non-peach pale pixel inside
    def cuff_box(x0, y0, x1, y1):
        m = Image.new("L", im.size, 0)
        mp = m.load()
        for y in range(y0, y1):
            for x in range(x0, x1):
                r, g, b, a = p[x, y]
                if a > 100 and min(r, g, b) > 150 and b >= g - 3 and max(r, g, b) - min(r, g, b) <= 34:
                    mp[x, y] = 255
        return m.filter(ImageFilter.MaxFilter(3))
    # the frill spills a few pixels past the tight box; leaving it behind puts
    # a white crumb on the torso when the arm swings away
    mk["cuff_L"] = cuff_box(302, 646, 362, 712)
    mk["cuff_R"] = cuff_box(575, 646, 638, 712)

    for side, poly, cuff_key in (("L", HAND_L, "cuff_L"), ("R", HAND_R, "cuff_R")):
        hp = poly_mask(im.size, poly, 1)
        hpp = hp.load()
        m = Image.new("L", im.size, 0)
        mp = m.load()
        for y in range(660, 720):
            for x in range(W):
                if not hpp[x, y] or ap[x, y] < 120:
                    continue
                if is_skin(*p[x, y]):
                    mp[x, y] = 255
        m = m.filter(ImageFilter.MaxFilter(5))
        m = ImageChops.multiply(m, invert(mk[cuff_key].filter(ImageFilter.MaxFilter(5))))
        m = ImageChops.multiply(m, poly_mask(im.size, poly, 2))
        mk["hand_" + ("l" if side == "L" else "r")] = m

    # grow every arm mask by the same 2 px: the layer, the body cut and the
    # skirt cut all use one mask, so no anti-aliased rim is left behind on the
    # torso when the arm swings away
    for key in ("sleeve_L", "sleeve_R", "cuff_L", "cuff_R"):
        mk[key] = mk[key].filter(ImageFilter.MaxFilter(5))

    # The gold cuff trim hugs the sleeve but is not navy, so the sleeve flood
    # missed it and it stayed in the skirt: raising the arm left an orange bar
    # standing at the hip.  Any gold touching the sleeve/cuff belongs to the
    # arm, so move it there (and out of every layer the arm cuts).
    for side, cuff_key in (("L", "cuff_L"), ("R", "cuff_R")):
        near = union(mk["sleeve_" + side], mk[cuff_key]).filter(ImageFilter.MaxFilter(7))
        npx = near.load()
        tr = Image.new("L", im.size, 0)
        tp = tr.load()
        for y in range(560, 760):
            for x in range(W):
                r, g, b, a = p[x, y]
                if (a > 120 and npx[x, y] and r > 170 and 110 < g < 205
                        and b < 130 and r - b > 70):
                    tp[x, y] = 255
        mk["trim_" + side.lower()] = tr.filter(ImageFilter.MaxFilter(3))
    mk["arm_l"] = union(mk["sleeve_L"], mk["cuff_L"], mk["trim_l"])
    mk["arm_r"] = union(mk["sleeve_R"], mk["cuff_R"], mk["trim_r"])
    mk["arms"] = union(mk["arm_l"], mk["arm_r"], mk["hand_l"], mk["hand_r"])
    return mk


# The dress area the arms cover.  Wide enough to take the 2 px grown arm mask
# (the bbox of the unit is 307..633 x 546..706) plus the blur radius.
PLATE_TOP = 532
PLATE_BOT = 722
PLATE_OUTLINE = (24, 32, 68, 255)


def dress_plate(im, p, ap, mk, hair_masks, tail):
    """Rebuild the dress hidden by the arms as clean, seamless navy.

    The old approach cut the arms out and interpolated the hole from its row /
    column neighbours, which dragged apron white into the sleeve footprint and
    left blue-white bars.  Interpolating per row instead produced a slightly
    different navy on every row, i.e. horizontal stripes as soon as an arm was
    raised.  So: measure the dress dye once over wide bands, low-pass that
    vertical curve, and paint the whole sleeve footprint with it, carrying the
    gold hem line through the hole and restoring the silhouette contour.
    """
    W, H = im.size
    armp = mk["arms"].load()
    hl = hair_masks["hair_l"].load()
    hr = hair_masks["hair_r"].load()
    tp = tail.load()

    def dye(r, g, b, a):
        # strictly the dress navy: the pale apron, the vivid apron emblem and
        # the blue hip ribbons all pass is_blue() and would pull the sample
        return (a > 200 and r < 70 and g < 80 and 95 < b < 155
                and b - r > 45 and not is_skin(r, g, b, a)
                and not is_pale(r, g, b, a) and not is_outline(r, g, b, a))

    def band_median(y0, y1):
        cols = []
        for y in range(y0, y1):
            for x in range(300, 640):
                if armp[x, y] or hl[x, y] or hr[x, y] or tp[x, y] or ap[x, y] < 150:
                    continue
                if dye(*p[x, y]):
                    cols.append(p[x, y][:3])
        cols.sort(key=lambda c: c[0] + c[1] + c[2])
        return cols[len(cols) // 2] if cols else (40, 56, 120)

    step = 24
    ys, cs = [], []
    for y0 in range(470, 890, step):
        ys.append(y0 + step * 0.5)
        cs.append(band_median(y0, y0 + step))

    raw = {}
    for y in range(PLATE_TOP, PLATE_BOT + 1):
        if y <= ys[0]:
            c = cs[0]
        elif y >= ys[-1]:
            c = cs[-1]
        else:
            i = 0
            while i + 1 < len(ys) and ys[i + 1] < y:
                i += 1
            t = (y - ys[i]) / (ys[i + 1] - ys[i])
            c = tuple(cs[i][k] + (cs[i + 1][k] - cs[i][k]) * t for k in range(3))
        raw[y] = c
    # low-pass the curve so band edges cannot survive as stripes
    soft_y = {}
    for y in range(PLATE_TOP, PLATE_BOT + 1):
        acc = [0.0, 0.0, 0.0]
        n = 0
        for yy in range(max(PLATE_TOP, y - 30), min(PLATE_BOT, y + 30) + 1):
            for k in range(3):
                acc[k] += raw[yy][k]
            n += 1
        soft_y[y] = tuple(acc[k] / n for k in range(3))

    plate = im.copy()
    pl = plate.load()
    for y in range(PLATE_TOP, PLATE_BOT + 1):
        c = soft_y[y]
        col = (int(c[0] + 0.5), int(c[1] + 0.5), int(c[2] + 0.5), 255)
        for x in range(W):
            if armp[x, y] and ap[x, y] > 8:
                pl[x, y] = col

    def is_gold(r, g, b, a):
        return a > 150 and r > 165 and 105 < g < 205 and b < 135 and r - b > 65

    # carry the gold hem through the sleeve: only where visible trim of the
    # same row sits just beside the hole on both sides, so a bow at one edge
    # cannot draw a false line
    for y in range(668, PLATE_BOT):
        x = 280
        spans = []
        while x < 660:
            if armp[x, y] and ap[x, y] > 8:
                x0 = x
                while x < 660 and armp[x, y] and ap[x, y] > 8:
                    x += 1
                spans.append((x0, x - 1))
            else:
                x += 1
        for x0, x1 in spans:
            left = right = None
            for xx in range(x0 - 1, max(279, x0 - 45), -1):
                if pl[xx, y][3] > 8 and not armp[xx, y] and is_gold(*pl[xx, y]):
                    left = xx
                    break
            for xx in range(x1 + 1, min(660, x1 + 45)):
                if pl[xx, y][3] > 8 and not armp[xx, y] and is_gold(*pl[xx, y]):
                    right = xx
                    break
            if left is None or right is None:
                continue
            for xx in range(x0, x1 + 1):
                pl[xx, y] = (245, 204, 110, 255)

    # soften only painted cloth, never the untouched art
    soft = plate.filter(ImageFilter.GaussianBlur(1.0))
    spx = soft.load()
    for y in range(PLATE_TOP, PLATE_BOT + 1):
        for x in range(W):
            if armp[x, y] and ap[x, y] > 8:
                pl[x, y] = spx[x, y]

    # restore the silhouette contour the artwork had around the hand
    for y in range(PLATE_TOP, PLATE_BOT + 1):
        for x in range(W):
            if not armp[x, y] or ap[x, y] < 40:
                continue
            if ((x > 1 and ap[x - 2, y] < 40) or (x + 2 < W and ap[x + 2, y] < 40)
                    or (y > 1 and ap[x, y - 2] < 40) or (y + 2 < H and ap[x, y + 2] < 40)):
                pl[x, y] = PLATE_OUTLINE
    return plate


def build_layers(im):
    W, H = im.size
    p = im.load()
    ap = im.getchannel("A").load()
    mk = build_masks(im, p, ap, W, H)
    raw = {}

    # ---- tail
    tail = poly_mask(im.size, TAIL_POLYGON, 1)
    tp = tail.load()
    for y in range(H):
        for x in range(W):
            if not tp[x, y]:
                continue
            r, g, b, a = p[x, y]
            if a <= 12 or is_skin(r, g, b, a) or is_pale(r, g, b, a) or is_outline(r, g, b, a):
                tp[x, y] = 0
    # grow by 2 px: the contour belongs to the tail, otherwise a dark rim of it
    # stays behind on the body and the skirt
    tail = tail.filter(ImageFilter.MaxFilter(5))
    raw["tail"] = apply_mask(im, tail)

    # ---- head
    head = Image.new("L", im.size, 0)
    hp = head.load()
    for y in range(0, HEAD_CUT + 1):
        for x in range(W):
            if ap[x, y] > 0:
                hp[x, y] = 255
    raw["head"] = apply_mask(im, head)

    # ---- long hair masks
    hair_masks = {}
    for name, poly in (("hair_l", LHAIR), ("hair_r", RHAIR)):
        pm = poly_mask(im.size, poly, 2)
        base = Image.new("L", im.size, 0)
        bp = base.load()
        pp = pm.load()
        for y in range(HEAD_CUT + 1, H):
            for x in range(W):
                if ap[x, y] < 50 or not pp[x, y]:
                    continue
                if is_hair(*p[x, y]) or is_hair_dark(*p[x, y]):
                    bp[x, y] = 255
        # the fin is drawn in front of the hair and carries near-white
        # highlights that pass the blue test; drop it so the hair layer holds
        # hair only and the hole behind the fin is filled from hair colour
        base = ImageChops.multiply(base, invert(tail))
        tpm = tail.load()
        grown = base.filter(ImageFilter.MaxFilter(5))
        gp = grown.load()
        for y in range(HEAD_CUT + 1, H):
            for x in range(W):
                if not gp[x, y] or bp[x, y] or not pp[x, y] or ap[x, y] < 50:
                    continue
                if tpm[x, y]:
                    continue
                # a wider blue test keeps the pale skirt frill (lavender white,
                # saturation ~25) out of the hair: it used to ride along with
                # the head and show up as a white sliver when the hair swung
                if is_pale(*p[x, y]) or is_skin(*p[x, y]):
                    continue
                if is_blue(*p[x, y]) and (max(p[x, y][:3]) - min(p[x, y][:3])) > 30:
                    bp[x, y] = 255
        # 2 px, matching the body cut so the hair keeps its own anti-aliased edge
        hair_masks[name] = base.filter(ImageFilter.MaxFilter(5))

    # ---- skirt mask
    skirt = Image.new("L", im.size, 0)
    sp = skirt.load()
    skp = poly_mask(im.size, SKIRT).load()
    app = poly_mask(im.size, APRON).load()
    for y in range(560, 850):
        for x in range(W):
            if ap[x, y] < 30:
                continue
            if skp[x, y]:
                sp[x, y] = 255
            elif app[x, y] and is_pale(*p[x, y]):
                sp[x, y] = 255
            elif 790 <= y < 850 and 310 <= x < 650 and is_pale(*p[x, y]):
                sp[x, y] = 255
    mk["skirt"] = skirt

    # ---- hair layers: cut arms + tail, inpaint the holes
    for name in ("hair_l", "hair_r"):
        lay = apply_mask(im, hair_masks[name])
        lay = cut(lay, mk["arms"])
        lay = cut(lay, tail)
        poly = LHAIR if name == "hair_l" else RHAIR
        pp = poly_mask(im.size, poly, 4).load()
        target = Image.new("L", im.size, 0)
        tg = target.load()
        lp = lay.load()
        afp = mk["arms"].load()
        tp2 = tail.load()
        for y in range(HEAD_CUT + 1, H):
            for x in range(W):
                if not pp[x, y] or lp[x, y][3] > 0:
                    continue
                if afp[x, y] or tp2[x, y]:
                    tg[x, y] = 255
        # The right arm hangs in front of the hair mass and the polygon stops
        # at the visible strands, so the sleeve area was never a fill target:
        # raising the arm uncovered the window.  Fill the whole right sleeve
        # (inner edge included) with hair as well.
        if name == "hair_r":
            armr = mk["arm_r"].load()
            for y in range(HEAD_CUT + 1, H):
                for x in range(W):
                    # only inside the painted silhouette: the arm mask is grown
                    # 2 px past the sleeve, and a fill there would ring the arm
                    if armr[x, y] and ap[x, y] > 8 and lp[x, y][3] <= 8:
                        tg[x, y] = 255
        raw[name] = blur_fill(lay, target)

    # ---- back hair: the whole lower-body painting, parked behind every other
    # layer.  The body and skirt are cut around the hair, so the moment the
    # head turns those cut-outs show the desktop; with this underneath they
    # uncover the original hair pixels instead.  The arm and fin art is
    # removed here (they draw on top and would otherwise leave a sleeve / fin
    # ghost when they move) and replaced with hair colour.
    back = im.copy()
    lower = Image.new("L", im.size, 0)
    ImageDraw.Draw(lower).rectangle((0, HEAD_CUT - 60, W, H), fill=255)
    back.putalpha(ImageChops.multiply(im.getchannel("A"), lower))
    # the band above the head cut is only there to back the hair that the
    # tilted head uncovers: drop the face / neck so nothing of the chin can
    # peek out under the cut edge
    bp4 = back.load()
    for y in range(HEAD_CUT - 60, HEAD_CUT + 1):
        for x in range(W):
            r, g, b, a = bp4[x, y]
            if a and not (b >= r and b > 120):
                bp4[x, y] = (r, g, b, 0)
    back = cut(back, mk["arms"])
    back = cut(back, tail)
    holes = Image.new("L", im.size, 0)
    hp3 = holes.load()
    bp3 = back.load()
    am3 = mk["arms"].load()
    tp3 = tail.load()
    for y in range(HEAD_CUT + 1, H):
        for x in range(W):
            if ((am3[x, y] or tp3[x, y]) and ap[x, y] > 8
                    and bp3[x, y][3] <= 8):
                hp3[x, y] = 255
    raw["hair_back"] = blur_fill(back, holes)

    # ---- body
    # The sleeves are no longer cut away and interpolated: the plate rebuilds
    # the dress they cover, so a raised arm uncovers clean cloth underneath
    # instead of bars, leftover cuff crumbs or torn sleeve edges.
    plate = dress_plate(im, p, ap, mk, hair_masks, tail)
    plp = plate.load()
    am = mk["arms"].load()
    body = cut(im, union(head, hair_masks["hair_l"], hair_masks["hair_r"], tail))
    bp = body.load()
    # neck / chest skin only: the shoulder corners are covered by the sleeves,
    # so they must stay cloth-coloured when an arm lifts away
    for y in range(496, HEAD_CUT + 1):
        for x in range(432, 510):
            if bp[x, y][3] < 8:
                t = (y - 496) / float(HEAD_CUT + 1 - 496)
                bp[x, y] = (int(253 - 6 * t), int(228 - 12 * t), int(220 - 14 * t), 255)
    # bake the plate into the sleeve footprint (the arms draw on top of it)
    for y in range(PLATE_TOP, PLATE_BOT + 1):
        for x in range(W):
            if am[x, y] and bp[x, y][3] > 8:
                bp[x, y] = plp[x, y]
    raw["body"] = body

    # ---- skirt layer: bake the same plate, then cut the tail (it passes in
    # front of the right edge) and fill only the tail holes.
    lay = apply_mask(im, skirt)
    lp = lay.load()
    for y in range(PLATE_TOP, PLATE_BOT + 1):
        for x in range(W):
            if am[x, y] and lp[x, y][3] > 8:
                lp[x, y] = plp[x, y]
    lay = cut(lay, tail)
    holes = Image.new("L", im.size, 0)
    hp2 = holes.load()
    lp = lay.load()
    tp2 = tail.load()
    # the tail reaches well past the dress; only fill where the skirt was
    # actually behind it, or a swinging fin uncovers a skirt-coloured blob
    # floating beside the hem
    skp = poly_mask(im.size, SKIRT, 2).load()
    for y in range(H):
        for x in range(W):
            if tp2[x, y] and lp[x, y][3] < 8 and skp[x, y]:
                hp2[x, y] = 255
    raw["skirt"] = fill_vertical(lay, holes)

    # ---- arms
    for side, tag in (("L", "l"), ("R", "r")):
        arm = union(mk["sleeve_" + side], mk["cuff_" + side], mk["trim_" + tag])
        # the hand's anti-aliased rim stays behind when the hand is cut out and
        # reads as an orange band once the wrist rotates, so widen the cut
        arm = ImageChops.multiply(arm, invert(mk["hand_" + tag].filter(ImageFilter.MaxFilter(7))))
        up = ImageChops.multiply(arm, band_mask(im.size, 0, 634))
        fore = ImageChops.multiply(arm, band_mask(im.size, 606, H))
        raw["arm_up_" + tag] = apply_mask(im, up)
        raw["arm_fore_" + tag] = apply_mask(im, fore)

    raw["hand_l"] = apply_mask(im, mk["hand_l"])
    raw["hand_rest"] = apply_mask(im, mk["hand_r"])

    raw.update(build_face(im, p))
    raw.update(build_props())

    out = {}
    for name, img in raw.items():
        bb = img.getchannel("A").getbbox()
        if not bb:
            raise ValueError("empty layer " + name)
        x0, y0, x1, y1 = bb
        x0, y0 = max(0, x0 - PAD), max(0, y0 - PAD)
        x1, y1 = min(W, x1 + PAD), min(H, y1 + PAD)
        out[name] = (img.crop((x0, y0, x1, y1)), (x0, y0, x1, y1))
    return out, mk, hair_masks


# ---------------------------------------------------------------- face

def mask_pick(mask, seed):
    """Keep only the 4-connected region of a binary mask that contains seed."""
    W, H = mask.size
    mp = mask.load()
    out = Image.new("L", (W, H), 0)
    op = out.load()
    if not (0 <= seed[0] < W and 0 <= seed[1] < H) or not mp[seed[0], seed[1]]:
        return out
    op[seed[0], seed[1]] = 255
    q = deque([seed])
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and mp[nx, ny] and not op[nx, ny]:
                op[nx, ny] = 255
                q.append((nx, ny))
    return out


def mask_holes(mask):
    """Fill every enclosed hole in a binary mask (the pupil is one)."""
    W, H = mask.size
    mp = mask.load()
    outside = Image.new("L", (W, H), 0)
    op = outside.load()
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if not mp[x, y] and not op[x, y]:
                op[x, y] = 255
                q.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if not mp[x, y] and not op[x, y]:
                op[x, y] = 255
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and not mp[nx, ny] and not op[nx, ny]:
                op[nx, ny] = 255
                q.append((nx, ny))
    out = mask.copy()
    outp = out.load()
    for y in range(H):
        for x in range(W):
            if not op[x, y]:
                outp[x, y] = 255
    return out


def smooth_path(pts, steps=8):
    """Catmull-Rom through 2-D control points, for lash curves."""
    if len(pts) < 3:
        return [tuple(p[:2]) for p in pts]
    ext = [pts[0]] + list(pts) + [pts[-1]]
    out = []
    for i in range(len(ext) - 3):
        p0, p1, p2, p3 = ext[i], ext[i + 1], ext[i + 2], ext[i + 3]
        for s in range(steps):
            t = s / float(steps)
            t2, t3 = t * t, t * t * t
            out.append(tuple(
                0.5 * ((2 * p1[k]) + (-p0[k] + p2[k]) * t
                       + (2 * p0[k] - 5 * p1[k] + 4 * p2[k] - p3[k]) * t2
                       + (-p0[k] + 3 * p1[k] - 3 * p2[k] + p3[k]) * t3)
                for k in (0, 1)))
    out.append(tuple(pts[-1][:2]))
    return out


def width_at(t, knots):
    """Piecewise-linear brush width from (t, width) knots."""
    if t <= knots[0][0]:
        return knots[0][1]
    for i in range(len(knots) - 1):
        t0, w0 = knots[i]
        t1, w1 = knots[i + 1]
        if t <= t1:
            if t1 == t0:
                return w1
            return w0 + (w1 - w0) * (t - t0) / (t1 - t0)
    return knots[-1][1]


def build_face(im, sp, registered=False):
    """Face layers, composed from clean parts instead of moved pixels.

    The previous version shifted the original iris around inside a copy of
    the eye, so the vacated iris left white stair-steps and the redrawn
    highlight poked out of the lid; the lid poses then covered the eye with a
    flat skin ellipse that left the old iris showing under it.  Here the eye
    is split into a skin base, a sclera, an iris disc cut from the art and
    repaired to a full circle, and the lash line.  Every pose is composited
    from those, so no old iris survives and every edge is anti-aliased.
    """
    fx0, fy0, fx1, fy1 = FACE_RECT
    crop = im.crop(FACE_RECT).convert("RGBA")
    CW, CH = crop.size
    SS = 4

    def full(img):
        c = Image.new("RGBA", im.size, (0, 0, 0, 0))
        c.alpha_composite(img, (fx0, fy0))
        return c

    out = {"eyes_open": full(crop)}

    # Measured off the art (source coords).  The iris is a near-circle that
    # fills most of the opening; the lash band runs above it and wings out
    # past the outer corner, where the sketch turns reddish.
    EYE_CLIP = {"L": (407.5, 457.5, 35.0, 23.5), "R": (539.5, 457.5, 35.0, 23.5)}
    # the lash reaches further out than the opening: its wing sits past the
    # outer corner, so the dark mask uses a wider search ellipse
    LASH_CLIP = {"L": (407.5, 455.0, 46.0, 27.0), "R": (539.5, 455.0, 46.0, 27.0)}
    IRIS_C = {"L": (410.0, 457.5), "R": (537.0, 457.5)}
    IRIS_R = (23.2, 22.2)
    MIRROR = 947.0
    SCLERA = (251, 249, 248)
    LASH = (28, 14, 15)
    LASH_WARM = (126, 56, 50)
    if registered:
        EYE_CLIP["L"] = (420.0, 457.5, 35.0, 23.5)
        LASH_CLIP["L"] = (420.0, 443.0, 55.0, 34.0)
        LASH_CLIP["R"] = (539.5, 443.0, 55.0, 34.0)
        IRIS_C["L"] = (420.0, 457.5)
        IRIS_C["R"] = (540.0, 457.5)

    def side_x(side, x):
        return (x + (10 if registered else 0)) if side == "L" else MIRROR - x + (3 if registered else 0)

    def eye_pixels(side):
        """Opening and lash masks for one eye, in face-crop coordinates."""
        cx, cy, rx, ry = EYE_CLIP[side]
        lx, ly, lrx, lry = LASH_CLIP[side]
        raw = Image.new("L", (CW, CH), 0)
        lash = Image.new("L", (CW, CH), 0)
        rp, lp = raw.load(), lash.load()
        for y in range(fy0, fy1):
            for x in range(fx0, fx1):
                r, g, b, a = sp[x, y]
                if a < 200:
                    continue
                white = min(r, g, b) > 230 and r - b < 16
                blue = b > r + 20 and b > 70
                dark = max(r, g, b) < 150 and g < 95
                near = ((x - cx) / (rx + 4.0)) ** 2 + ((y - cy) / (ry + 4.0)) ** 2 <= 1.0
                if near and (white or blue):
                    rp[x - fx0, y - fy0] = 255
                elif dark and ((x - lx) / lrx) ** 2 + ((y - ly) / lry) ** 2 <= 1.0:
                    lp[x - fx0, y - fy0] = 255
        seed = (int(IRIS_C[side][0]) - fx0, int(IRIS_C[side][1]) - fy0)
        opening = mask_holes(mask_pick(raw, seed))
        # The lash band sits between the eye and the bangs; the pupil is the
        # only dark thing inside the iris, so keep it out of the lash sprite.
        ix, iy = IRIS_C[side]
        ip = lash.load()
        for y in range(fy0, fy1):
            for x in range(fx0, fx1):
                if ((x - ix) / IRIS_R[0]) ** 2 + ((y - iy) / IRIS_R[1]) ** 2 <= 1.0:
                    ip[x - fx0, y - fy0] = 0
        return opening, lash

    openings, lashes = {}, {}
    for side in ("L", "R"):
        openings[side], lashes[side] = eye_pixels(side)

    def union_masks(*masks):
        out_m = Image.new("L", (CW, CH), 0)
        op = out_m.load()
        for m in masks:
            mp = m.load()
            for y in range(CH):
                for x in range(CW):
                    if mp[x, y]:
                        op[x, y] = 255
        return out_m

    # Fill a hole with the skin around it.  One average colour reads as a
    # pasted ellipse, so blur the surrounding skin in from the edge instead:
    # the cheek shading and the boundary tone stay continuous.
    def fill_skin(img, hole):
        field = Image.new("RGBA", img.size, (0, 0, 0, 0))
        fp = field.load()
        ip, hp = img.load(), hole.load()
        for y in range(img.height):
            for x in range(img.width):
                r, g, b, a = ip[x, y]
                if (a > 200 and not hp[x, y] and r > 200 and g > 168
                        and r - b < 42 and b - g < 12):
                    fp[x, y] = (r, g, b, 255)
        out_img = img.copy()
        p = out_img.load()
        coords = [(x, y) for y in range(img.height) for x in range(img.width)
                  if hp[x, y]]
        for r in (44, 30, 20, 13, 8, 4, 2):
            bl = field.filter(ImageFilter.GaussianBlur(r)).load()
            for x, y in coords:
                a = bl[x, y][3]
                if a > 4:
                    c = (min(255, bl[x, y][0] * 255 // a),
                         min(255, bl[x, y][1] * 255 // a),
                         min(255, bl[x, y][2] * 255 // a), 255)
                    p[x, y] = c
                    fp[x, y] = c
        return out_img

    def base_with(hole):
        """The crop with `hole` punched out and refilled with cheek skin."""
        img = crop.copy()
        p = img.load()
        hp = hole.load()
        for y in range(CH):
            for x in range(CW):
                if hp[x, y]:
                    p[x, y] = (0, 0, 0, 0)
        return fill_skin(img, hole)

    eye_hole = union_masks(*[openings[s].filter(ImageFilter.MaxFilter(3))
                             for s in ("L", "R")])
    lid_hole = union_masks(eye_hole,
                           *[lashes[s].filter(ImageFilter.MaxFilter(3))
                             for s in ("L", "R")])
    base_eye = base_with(eye_hole)
    base_lid = base_with(lid_hole)

    def art_sprite(mask):
        """The original art pixels inside a mask, softly cut."""
        m = mask.filter(ImageFilter.MaxFilter(3))
        spr = crop.copy()
        spr.putalpha(ImageChops.multiply(spr.getchannel("A"), m))
        return spr

    lash_spr = {s: art_sprite(lashes[s]) for s in ("L", "R")}
    open_soft = {s: openings[s].filter(ImageFilter.GaussianBlur(0.6))
                 for s in ("L", "R")}

    def iris_sprite(side):
        """The art's iris as a full, clean disc.

        In the art the iris is clipped by the lash on top and the lower lid
        below, so the columns are extended with their own edge colour: a
        full disc can then be moved without dragging lash or skin with it.
        """
        cx, cy = IRIS_C[side]
        rx, ry = IRIS_R
        lx, ly = cx - fx0, cy - fy0
        disc = Image.new("L", (CW * SS, CH * SS), 0)
        ImageDraw.Draw(disc).ellipse(((lx - rx) * SS, (ly - ry) * SS,
                                      (lx + rx) * SS, (ly + ry) * SS), fill=255)
        alpha = disc.resize((CW, CH), Image.BOX)
        spr = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        px, ap = spr.load(), alpha.load()
        cols = {}
        for y in range(CH):
            for x in range(CW):
                av = ap[x, y]
                if av == 0:
                    continue
                r, g, b, a = sp[x + fx0, y + fy0]
                if a < 200:
                    continue
                deep = ((x - lx) / rx) ** 2 + ((y - ly) / ry) ** 2 < 0.88 ** 2
                irisish = (b > r + 12 and b > 45) or max(r, g, b) < 110
                if irisish or (deep and min(r, g, b) > 226):
                    px[x, y] = (r, g, b, av)
                    cols.setdefault(x, []).append(y)
        for x, ys in cols.items():
            y0, y1 = min(ys), max(ys)
            for y in range(CH):
                if ap[x, y] == 0:
                    continue
                if y < y0:
                    px[x, y] = px[x, y0][:3] + (ap[x, y],)
                elif y > y1:
                    px[x, y] = px[x, y1][:3] + (ap[x, y],)
        return spr

    iris_spr = {s: iris_sprite(s) for s in ("L", "R")}

    def shifted(img, dx, dy):
        out_img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        out_img.paste(img, (int(dx), int(dy)))
        return out_img

    def sclera_layer(side):
        """White of the eye: cool shadow at the top, warm light at the bottom.

        A flat white disc under the lash is the brightest thing on the face
        and reads as a sticker once the iris slides off it.
        """
        op = openings[side].load()
        ys = [y for y in range(CH) if any(op[x, y] for x in range(CW))]
        top, bot = (min(ys), max(ys)) if ys else (0, CH)
        img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        p = img.load()
        span = max(1, bot - top)
        for y in range(top, bot + 1):
            f = (y - top) / float(span)
            c = (int(237 + 14 * f), int(240 + 6 * f), int(248 - 6 * f), 255)
            for x in range(CW):
                p[x, y] = c
        img.putalpha(open_soft[side])
        return img

    def lid_shadow(side, depth=7, strength=0.34):
        """The lid's shadow on the white just under the upper lash."""
        op = open_soft[side].load()
        sh = Image.new("L", (CW, CH), 0)
        sp_ = sh.load()
        for x in range(CW):
            top = None
            for y in range(CH):
                if op[x, y] > 110:
                    top = y
                    break
            if top is None:
                continue
            for y in range(top, min(CH, top + depth)):
                f = 1.0 - (y - top) / float(depth)
                sp_[x, y] = int(255 * strength * f * (op[x, y] / 255.0))
        return sh

    def eye_parts(img, dy=0, dx=0, clip=None, draw_lashes=True):
        """Sclera + iris + lash for both eyes, into `img`."""
        for side in ("L", "R"):
            img.alpha_composite(sclera_layer(side))
            # a flat white ring around the iris reads as a sticker, so shade
            # the white where the lid and the iris would fall on it
            shade = Image.new("RGBA", (CW, CH), (48, 62, 104, 255))
            shade.putalpha(lid_shadow(side))
            img.alpha_composite(shade)
            ir = shifted(iris_spr[side], dx, dy)
            a = ImageChops.multiply(ir.getchannel("A"),
                                    clip[side] if clip else open_soft[side])
            ir.putalpha(a)
            ring = ImageChops.subtract(
                ir.getchannel("A").filter(ImageFilter.GaussianBlur(2.6)),
                ir.getchannel("A"))
            ring = ImageChops.multiply(ring, open_soft[side])
            ring = ring.point(lambda v: v * 110 // 255)
            sh2 = Image.new("RGBA", (CW, CH), (40, 52, 96, 255))
            sh2.putalpha(ring)
            img.alpha_composite(sh2)
            img.alpha_composite(ir)
            if draw_lashes:
                img.alpha_composite(lash_spr[side])
        return img

    # ---- glance poses: the iris moves, the lid and lash stay put
    for name, (dx, dy) in {"left": (-5, 0), "right": (5, 0),
                           "up": (0, -3), "down": (0, 3)}.items():
        img = eye_parts(base_eye.copy(), dx=dx, dy=dy)
        out["eyes_" + name] = full(img)

    # ---- lid poses.  Drawn in left-eye coordinates and mirrored.
    def curve(side, pts):
        return [(side_x(side, x) - fx0, y - fy0) for x, y in pts]

    def stroke(pts, knots, color, tip=None):
        big = Image.new("RGBA", (CW * SS, CH * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        path = smooth_path(pts, 8)
        n = max(1, len(path) - 1)
        for i, (x, y) in enumerate(path):
            t = i / float(n)
            w = width_at(t, knots)
            c = color
            if tip is not None and t > 0.76:
                f = (t - 0.76) / 0.24
                c = tuple(int(color[k] + (tip[k] - color[k]) * f) for k in range(3))
            d.ellipse(((x - w) * SS, (y - w) * SS, (x + w) * SS, (y + w) * SS),
                      fill=c + (255,))
        return big.resize((CW, CH), Image.BOX)

    # The lash is drawn from the inner corner out over the lid and then flicks
    # up past the outer corner; the art's own wing is erased first, so each
    # pose gets one continuous line instead of a stroke over a second lash.
    HALF = ([(440, 451), (426, 446), (410, 445), (394, 448), (379, 455)],
            [(379, 455), (371, 451), (364, 445)])
    CLOSED = ([(440, 459), (426, 454), (410, 453), (394, 456), (379, 461)],
              [(379, 461), (371, 457), (363, 451)])
    HAPPY = ([(437, 464), (423, 452), (410, 446), (397, 452), (383, 464)],
             [])

    def lid_variant(base, arcs, cover_all=False):
        img = base.copy() if cover_all else eye_parts(base.copy(), draw_lashes=False)
        # put the skin back over the lid: the base already holds exactly the
        # right cheek tone there, so no second fill is invented
        if cover_all:
            above = union_masks(*[open_soft[s] for s in ("L", "R")])
        else:
            above = Image.new("L", (CW, CH), 0)
            d = ImageDraw.Draw(above)
            for side in ("L", "R"):
                p = curve(side, arcs[0])
                d.polygon(p + [(p[-1][0], 0), (p[0][0], 0)], fill=255)
            above = ImageChops.multiply(above, union_masks(
                *[open_soft[s] for s in ("L", "R")]))
        img.paste(base, (0, 0), above)
        for side in ("L", "R"):
            arc, wing = arcs
            img.alpha_composite(stroke(
                curve(side, arc),
                [(0.0, 0.8), (0.12, 2.5), (0.5, 3.3), (0.82, 2.7), (1.0, 2.0)],
                LASH))
            if wing:
                img.alpha_composite(stroke(
                    curve(side, wing), [(0.0, 2.0), (0.55, 1.3), (1.0, 0.2)],
                    LASH, LASH_WARM))
        return img

    out["eyes_half"] = full(lid_variant(base_lid, HALF))
    # closed: the whole opening is lid, so no iris may peek under the lash
    out["eyes_closed"] = full(lid_variant(base_lid, CLOSED, cover_all=True))
    out["eyes_happy"] = full(lid_variant(base_lid, HAPPY, cover_all=True))

    # ---- mouth: erase the drawn mouth with the local skin, then redraw
    mx0, my0, mx1, my1 = MOUTH_RECT
    mbase = im.crop(MOUTH_RECT).convert("RGBA")
    MW, MH = mbase.size

    def mfull(img):
        c = Image.new("RGBA", im.size, (0, 0, 0, 0))
        c.alpha_composite(img, (mx0, my0))
        return c

    out["mouth_default"] = mfull(mbase)

    erase = Image.new("L", (MW, MH), 0)
    ImageDraw.Draw(erase).rounded_rectangle((13, 9, 36, 25), radius=7, fill=255)
    erase = erase.filter(ImageFilter.GaussianBlur(1.0))
    mimg = mbase.copy()
    mp = mimg.load()
    ep = erase.load()
    for y in range(MH):
        for x in range(MW):
            if ep[x, y] > 128:
                mp[x, y] = (0, 0, 0, 0)
    mskin = fill_skin(mimg, erase)

    MOUTH_C = (24.5, 16.5)

    def mouth(kind):
        img = mskin.copy()
        big = Image.new("RGBA", (MW * SS, MH * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(big)
        cx, cy = MOUTH_C
        if kind == "sip":
            # a small open mouth: dark interior, lit lower lip, soft upper line
            d.ellipse(((cx - 4.2) * SS, (cy - 3.4) * SS,
                       (cx + 4.2) * SS, (cy + 3.6) * SS), fill=(156, 62, 66, 255))
            d.ellipse(((cx - 3.0) * SS, (cy + 0.2) * SS,
                       (cx + 3.0) * SS, (cy + 3.0) * SS), fill=(204, 104, 102, 255))
            d.ellipse(((cx - 1.2) * SS, (cy + 1.4) * SS,
                       (cx + 0.6) * SS, (cy + 2.6) * SS), fill=(238, 176, 170, 255))
        else:
            path = smooth_path([(17.0, 14.6), (24.5, 18.6), (32.0, 14.6)], 10)
            for x, y in path:
                d.ellipse(((x - 1.15) * SS, (y - 1.15) * SS,
                           (x + 1.15) * SS, (y + 1.15) * SS),
                          fill=(210, 84, 88, 255))
            for x, y in path[4:-4]:
                d.ellipse(((x - 0.5) * SS, (y + 0.8) * SS,
                           (x + 0.5) * SS, (y + 1.9) * SS),
                          fill=(246, 176, 170, 255))
        img.alpha_composite(big.resize((MW, MH), Image.BOX))
        return mfull(img)

    out["mouth_sip"] = mouth("sip")
    out["mouth_smile"] = mouth("smile")
    return out


# ---------------------------------------------------------------- props

def build_props():
    cream = (250, 246, 236, 255)
    cream_d = (226, 214, 196, 255)
    navy = (42, 55, 122, 255)
    line = (30, 34, 58, 255)
    skin = (254, 238, 230, 255)
    shade = (240, 205, 195, 255)
    crease = (222, 168, 158, 255)
    dark = (120, 70, 60, 255)
    gold = (216, 170, 70, 255)

    # Props are drawn at 3x and downsampled: they are tiny on screen and the
    # 1x ImageDraw ellipses were leaving jagged, "paw-like" hands.
    S = 3
    SS = float(S)

    class Brush:
        def __init__(self, img):
            # kept so a prop can composite a raster sprite (the official whale)
            # onto the same supersampled canvas
            self.img = img
            self.d = ImageDraw.Draw(img)

        @staticmethod
        def _kw(kw):
            if "width" in kw:
                kw["width"] = max(1, int(round(kw["width"] * SS)))
            return kw

        def ellipse(self, box, **kw):
            self.d.ellipse([v * SS for v in box], **self._kw(kw))

        def rect(self, box, **kw):
            self.d.rectangle([v * SS for v in box], **self._kw(kw))

        def rrect(self, box, r, **kw):
            self.d.rounded_rectangle([v * SS for v in box], radius=r * SS,
                                     **self._kw(kw))

        def poly(self, pts, **kw):
            self.d.polygon([(x * SS, y * SS) for x, y in pts], **self._kw(kw))

        def line(self, pts, width, **kw):
            self.d.line([(x * SS, y * SS) for x, y in pts], width=max(1, int(width * SS)), **kw)

        def capsule(self, x0, y0, x1, y1, r, fill=None, outline=None, width=1):
            dx, dy = x1 - x0, y1 - y0
            n = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / n * r, dx / n * r
            poly = [(x0 + nx, y0 + ny), (x1 + nx, y1 + ny),
                    (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)]
            self.poly(poly, fill=fill, outline=outline,
                      width=max(1, int(width * SS)) if outline else 0)
            self.ellipse((x0 - r, y0 - r, x0 + r, y0 + r), fill=fill,
                         outline=outline, width=max(1, int(width * SS)) if outline else 0)
            self.ellipse((x1 - r, y1 - r, x1 + r, y1 + r), fill=fill,
                         outline=outline, width=max(1, int(width * SS)) if outline else 0)

    def canvas(fn):
        img = Image.new("RGBA", (1024 * S, 1024 * S), (0, 0, 0, 0))
        fn(Brush(img))
        return img.resize((1024, 1024), Image.LANCZOS)

    # ---- transparent water bottle.  The glass body sits in front of the
    # separate water layer; the neck is open (the cap is off while drinking).
    def bottle(p):
        p.poly([(430, 592), (442, 574), (498, 574), (510, 592)],
               fill=(208, 238, 250, 60), outline=(58, 102, 135, 215), width=2)
        p.rrect((430, 592, 510, 660), 10, fill=(208, 238, 250, 60),
                outline=(58, 102, 135, 215), width=2)
        p.rect((452, 566, 488, 578), fill=(214, 240, 250, 70),
               outline=(58, 102, 135, 215), width=2)
        p.ellipse((450, 556, 490, 568), fill=(225, 243, 251, 90),
                  outline=(58, 102, 135, 230), width=2)
        p.ellipse((456, 559, 484, 565), fill=(70, 115, 145, 120))
        # screw thread ring
        p.rect((452, 570, 488, 575), fill=(225, 243, 251, 120),
               outline=(58, 102, 135, 160), width=1)
        # highlights + a couple of bubbles in the glass
        p.rrect((438, 600, 446, 648), 4, fill=(255, 255, 255, 92))
        p.rrect((500, 608, 505, 644), 2, fill=(255, 255, 255, 58))
        p.ellipse((449, 634, 455, 640), fill=(255, 255, 255, 80))
        p.ellipse((460, 626, 464, 630), fill=(255, 255, 255, 60))

    def water(p):
        pts = [(434, 602)]
        for x in range(438, 507, 6):
            pts.append((x, 602 + 1.6 * math.sin((x - 434) * 0.55)))
        pts += [(506, 656), (434, 656)]
        p.poly(pts, fill=(104, 190, 232, 208))
        # bright surface band follows the same wave
        p.poly([(434, 602)] + [(x, 602 + 1.6 * math.sin((x - 434) * 0.55))
                               for x in range(438, 507, 6)] + [(506, 605), (434, 605)],
               fill=(176, 228, 250, 235))
        p.ellipse((446, 626, 452, 632), fill=(225, 245, 255, 110))
        p.ellipse((486, 640, 491, 645), fill=(225, 245, 255, 90))

    # ---- right grip hand, bound to gripR (the wrist) so it rides on the
    # bottle.  The fingers used to be four separately outlined rounded bars,
    # which read as parallel sticks at pet size; here they are drawn as one
    # merged silhouette and only the creases between them are darker, the way
    # a hand closing on a glass actually reads.
    def grip_hand(p):
        W = 1024 * S
        shape = Image.new("L", (W, W), 0)
        sd = ImageDraw.Draw(shape)

        def ell(box):
            sd.ellipse([v * S for v in box], fill=255)

        def rr(box, rad):
            sd.rounded_rectangle([v * S for v in box], radius=rad * S, fill=255)

        def cap(x0, y0, x1, y1, r):
            ax, ay, bx, by = x0 * S, y0 * S, x1 * S, y1 * S
            rr_ = r * S
            dx, dy = bx - ax, by - ay
            n = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / n * rr_, dx / n * rr_
            sd.polygon([(ax + nx, ay + ny), (bx + nx, by + ny),
                        (bx - nx, by - ny), (ax - nx, ay - ny)], fill=255)
            sd.ellipse([ax - rr_, ay - rr_, ax + rr_, ay + rr_], fill=255)
            sd.ellipse([bx - rr_, by - rr_, bx + rr_, by + rr_], fill=255)

        rr((512, 610, 534, 646), 8)          # wrist stump, under the cuff
        ell((504, 582, 540, 624))            # back of the hand
        # four fingers close over the glass; each is a little shorter, so the
        # row follows the bottle's curve instead of ending on one hard line
        cap(514, 588, 478, 586, 4.8)
        cap(514, 599, 476, 599, 4.8)
        cap(512, 610, 480, 611, 4.6)
        cap(508, 619, 486, 621, 4.2)
        cap(526, 585, 496, 597, 5.4)         # thumb laid over the top fingers

        img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        img.paste(Image.new("RGBA", (W, W), dark), (0, 0),
                  shape.filter(ImageFilter.MaxFilter(5)))
        img.paste(Image.new("RGBA", (W, W), skin), (0, 0), shape)
        # creases (not outlines) between the fingers, and the shadow the thumb
        # casts across the knuckles
        soft = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(soft)
        for y in (593, 604, 615):
            d2.line([(484 * S, y * S), (510 * S, y * S)],
                    fill=(226, 182, 172, 235), width=max(2, int(1.3 * S)))
        d2.ellipse([508 * S, 600 * S, 520 * S, 612 * S], fill=(238, 198, 190, 255))
        soft.putalpha(ImageChops.multiply(soft.getchannel("A"), shape))
        img.alpha_composite(soft)
        return img.resize((1024, 1024), Image.LANCZOS)

    # ---- left grip hand: mirror the right around the character centre x=470
    # (flip around x=512 then shift by -84).
    grip_r_img = grip_hand(None)
    grip_l = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    grip_l.paste(grip_r_img.transpose(Image.FLIP_LEFT_RIGHT), (-84, 0))

    # ---- notebook: a closed black memo pad, back cover to the camera, with a
    # pale fish stamp.  The pen works over its top edge, so the writing hand
    # can stay hidden behind the pad.
    def book(p):
        # page block peeking out on the spine side
        p.rrect((418, 588, 432, 648), 4, fill=(238, 232, 218),
                outline=(176, 170, 158), width=1.5)
        for y in (596, 606, 616, 626, 636):
            p.line([(419, y), (431, y)], 1.0, fill=(206, 200, 186, 190))
        # back cover
        p.rrect((424, 583, 520, 649), 8, fill=(34, 36, 46), outline=(12, 13, 18), width=2)
        # spine side is a touch lighter, with a stitch line
        p.rrect((426, 585, 436, 647), 5, fill=(46, 49, 62))
        p.line([(433, 592), (433, 640)], 1.0, fill=(72, 76, 94, 210))
        # stitched border down the right edge
        for y in range(590, 646, 8):
            p.line([(516, y), (516, min(y + 4, 646))], 1.0, fill=(72, 76, 94, 210))
        # stamped mark: the official DeepSeek whale, one light colour printed
        # on the dark cover (its eye, mouth and belly cut are the cover
        # showing through, exactly like the upstream logo)
        mark = (238, 245, 255, 255)
        w = render_whale(int(36 * S), mark, ss=2)
        p.img.alpha_composite(w, (432 * S, 614 * S))
        # the top page lies open over the right half of the cover: she writes
        # on paper, not on the logo side of a closed pad.  Slightly skewed so
        # it reads as a sheet rather than a painted rectangle.
        p.poly([(474, 590), (516, 592), (516, 642), (474, 644)],
               fill=(250, 249, 244), outline=(198, 194, 182), width=1.2)
        p.line([(474, 590), (474, 644)], 2.0, fill=(214, 209, 196))
        for y in (601, 611, 621, 631, 639):
            p.line([(478, y), (511, y + 0.4)], 1.0, fill=(196, 206, 220, 170))
        # a few words already on the page's upper lines
        for x0, x1, y in ((479, 502, 601), (479, 495, 611), (479, 508, 631)):
            p.line([(x0, y), (x1, y)], 1.6, fill=(150, 158, 176, 130))
        # elastic closure, over the page it holds down
        p.rect((505, 583, 514, 649), fill=(22, 23, 30))
        p.line([(507, 589), (507, 646)], 1.0, fill=(56, 60, 76, 220))
        p.line([(512, 589), (512, 646)], 1.0, fill=(56, 60, 76, 220))
        # gold corner tab
        p.poly([(506, 643), (520, 643), (520, 649), (506, 649)], fill=gold)

    # ---- pen: the whole pen, lying on the cover rather than vanishing behind
    # its top edge.  The old art stopped at the book edge and left the nib in
    # mid air with no hand on the barrel; now the nib touches the cover at
    # (487,621) and the grip section at (512,609) is where hand_pen closes on it.
    def pen(p):
        # nib on the page at (484,624); the barrel runs up-right past the fist
        p.poly([(484, 624), (494, 622), (492, 615)], fill=(226, 232, 242, 255),
               outline=(120, 126, 140), width=1.2)
        p.line([(488, 621), (491, 618)], 1.0, fill=(252, 253, 255))
        p.capsule(493, 620, 543, 599, 4.2, fill=(92, 118, 178), outline=line, width=1.5)
        p.capsule(497, 618, 539, 601, 1.6, fill=(176, 198, 240, 170))
        p.capsule(491, 621, 496, 619, 3.8, fill=gold, outline=(150, 112, 52), width=1.2)
        p.ellipse((539, 594, 547, 602), fill=(64, 84, 132), outline=line, width=1.2)

    # ---- the hand that holds the pen.  Bound to the PEN bone, not the wrist
    # bone: the pen owns the writing motion, so the fist has to travel with it,
    # and a fist bound to handR would be swung by the IK-bent forearm.  The
    # wrist end sits on workR (532,598), where the cuff arrives, and the fingers
    # stop short of the nib so the tip stays visible on the page.
    def hand_pen():
        W = 1024 * S
        shape = Image.new("L", (W, W), 0)
        sd = ImageDraw.Draw(shape)

        def T(x, y):
            return (x * S, y * S)

        def ell(box):
            sd.ellipse([*T(box[0], box[1]), *T(box[2], box[3])], fill=255)

        def cap(x0, y0, x1, y1, r):
            ax, ay = T(x0, y0)
            bx, by = T(x1, y1)
            r = r * S
            dx, dy = bx - ax, by - ay
            n = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / n * r, dx / n * r
            sd.polygon([(ax + nx, ay + ny), (bx + nx, by + ny),
                        (bx - nx, by - ny), (ax - nx, ay - ny)], fill=255)
            sd.ellipse([ax - r, ay - r, ax + r, ay + r], fill=255)
            sd.ellipse([bx - r, by - r, bx + r, by + r], fill=255)

        # a small fist: the pen is only 4 px thick, and the first version at
        # full mitten size buried it completely
        K = 0.72
        GX, GY = 524.0, 608.0

        def T2(x, y):
            return ((GX + (x - GX) * K) * S, (GY + (y - GY) * K) * S)

        def cap2(x0, y0, x1, y1, r):
            ax, ay = T2(x0, y0)
            bx, by = T2(x1, y1)
            r = r * K * S
            dx, dy = bx - ax, by - ay
            n = math.hypot(dx, dy) or 1.0
            nx, ny = -dy / n * r, dx / n * r
            sd.polygon([(ax + nx, ay + ny), (bx + nx, by + ny),
                        (bx - nx, by - ny), (ax - nx, ay - ny)], fill=255)
            sd.ellipse([ax - r, ay - r, ax + r, ay + r], fill=255)
            sd.ellipse([bx - r, by - r, bx + r, by + r], fill=255)

        # wrist, palm, three fingers closing over the barrel and a thumb
        cap2(534, 602, 541, 599, 5.0)
        ell((514, 599, 538, 619))
        cap2(516, 605, 506, 612, 3.8)
        cap2(514, 611, 505, 618, 3.8)
        cap2(511, 617, 503, 622, 3.4)
        cap2(542, 594, 530, 598, 3.4)

        img = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        grown = shape.filter(ImageFilter.MaxFilter(5))
        img.paste(Image.new("RGBA", (W, W), line), (0, 0), grown)
        img.paste(Image.new("RGBA", (W, W), skin), (0, 0), shape)
        # no palm hollow: a blush circle in the middle of the fist reads as an
        # open palm facing the viewer.  Just a shadow under the fingers and one
        # crease between the knuckles.
        soft = Image.new("RGBA", (W, W), (0, 0, 0, 0))
        d2 = ImageDraw.Draw(soft)
        d2.ellipse([*T2(514, 610), *T2(530, 619)], fill=(236, 200, 192, 255))
        d2.line([*T2(519, 604), *T2(518, 612)], fill=(243, 210, 206, 210),
                width=max(1, int(0.8 * K * S)))
        soft.putalpha(ImageChops.multiply(soft.getchannel("A"), shape))
        img.alpha_composite(soft)
        return img.resize((1024, 1024), Image.LANCZOS)


    # ---- the slack prop: the official DeepSeek whale, held at the belly.
    # One piece on the `fish` bone -- the whole whale sways, so there is no
    # separate tail to drift off a different outline.
    # Coloured the way the official mark is drawn on a white ground: blue
    # body, white belly and face.  It sits over the apron emblem.
    # Sized to the body: the apron is 222 source px wide, so 200 makes the
    # plush read as "as wide as she is" at both the 340 px and the 170 px
    # display height.  The 100 px version shrank to a 20 px smudge at half
    # size.  Width 200 keeps the mark's own 1.359:1 ratio, which
    # render_whale_parts() enforces from the logo viewbox.
    # Sized against the reference pose: the plush is as long as her torso and
    # carried on the diagonal, head up-left near the chin and tail down-right
    # past the hip, so both arms have something to wrap around.  The diagonal
    # is baked into the art rather than keyed on the `fish` bone: rotating the
    # bone also rotated the two palms riding it, and the hands ended up
    # sideways on the plush.  Width keeps the mark's own 1.359:1 ratio.
    # Measured off the reference panel, where the plush fills the torso from
    # the chin to the belt and its fluke sticks out sideways past her sleeve.
    # The mark's own fluke points up-right, so the painted version is the mark
    # turned about 30 degrees clockwise; -14 left the fluke behind her
    # shoulder and the plush read as an egg.
    WHALE_W = 250
    WHALE_CX, WHALE_CY = 455, 632
    WHALE_ANGLE = 8.0
    WHALE_BODY = (72, 106, 240)
    WHALE_BELLY = (240, 246, 255)
    WHALE_RIM = (38, 54, 122)

    def fish(p):
        body, belly, details = render_whale_parts(WHALE_W * S)

        # draw flat on its own layer first so the whole plush can be turned
        # in one go, rim and face included
        pad = 3 * S
        spr = Image.new("RGBA", (body.width + pad * 2, body.height + pad * 2),
                        (0, 0, 0, 0))

        def put(mask, color):
            im = Image.new("RGBA", mask.size, color)
            im.putalpha(mask)
            spr.alpha_composite(im, (pad, pad))

        # a one-source-pixel navy rim: without it the plush dissolves into the
        # white apron below and into the pale emblem behind it
        rim = body.filter(ImageFilter.MaxFilter(2 * S + 1))
        put(rim, WHALE_RIM)
        put(body, WHALE_BODY)
        put(belly, WHALE_BELLY)
        # the belly sits slightly deeper at the bottom, so the plush is not flat
        shade = Image.new("L", belly.size, 0)
        sp2 = shade.load()
        for y in range(belly.height):
            sp2_y = int(110 * smoothstep(0.25, 1.0, y / float(belly.height - 1)))
            for x in range(belly.width):
                sp2[x, y] = sp2_y
        put(ImageChops.multiply(belly, shade), (176, 202, 250))
        # the eye and the smile are cut out of the mark; drawing them navy the
        # way the reference plush paints them keeps them off the white belly,
        # where they read as two specular blobs
        put(details, WHALE_RIM)

        spr = spr.rotate(WHALE_ANGLE, expand=True, resample=Image.BICUBIC)
        p.img.alpha_composite(spr, (int(WHALE_CX * S - spr.width * 0.5),
                                    int(WHALE_CY * S - spr.height * 0.5)))

    # ---- hands.  Cut from the artist's five-pose sheet by tools/hand_cut.py,
    # not drawn here.  The sheet already has this character's hands painted in
    # the poses the rig needs; anything built from ellipses reads as a sticker
    # next to the painted portrait.
    cuts = cut_hands()
    hand_props = {}
    for name, (src, kw) in HAND_PLACEMENTS.items():
        hand_props[name] = place_hand(*cuts[src], **kw)

    return {
        "bottle": canvas(bottle),
        "water": canvas(water),
        "hand_grip": grip_r_img,
        "hand_grip_l": grip_l,
        "book": canvas(book),
        "pen": canvas(pen),
        "hand_pen": hand_pen(),
        "fish": canvas(fish),
        "fish_hand_l": hand_props["fish_hand_l"],
        "fish_hand_r": hand_props["fish_hand_r"],
        "hand_open": hand_props["hand_open"],
        "hand_open_l": hand_props["hand_open_l"],
    }


# ---------------------------------------------------------------- meshes

def world_vert(x, y):
    return img_to_world(x, y)


def make_quad(rect, bone):
    x0, y0, x1, y1 = rect
    uvs, verts = [], []
    for (x, y, u, v) in ((x0, y0, 0, 0), (x1, y0, 1, 0), (x0, y1, 0, 1), (x1, y1, 1, 1)):
        uvs.extend((u, v))
        wx, wy = world_vert(x, y)
        ox, oy = bone_offset(bone, wx, wy)
        verts.extend((1, BONE_INDEX[bone], round(ox, 3), round(oy, 3), 1.0))
    tris = [0, 2, 3, 0, 3, 1]
    return {"type": "mesh", "uvs": uvs, "triangles": tris, "vertices": verts,
            "width": x1 - x0, "height": y1 - y0}


def make_grid(rect, grid, weight_fn):
    x0, y0, x1, y1 = rect
    cols = int(math.ceil((x1 - x0) / grid)) + 1
    rows = int(math.ceil((y1 - y0) / grid)) + 1
    xs = [min(x0 + i * grid, x1) for i in range(cols)]
    ys = [min(y0 + j * grid, y1) for j in range(rows)]
    uvs, verts = [], []
    for y in ys:
        for x in xs:
            uvs.append(round((x - x0) / float(x1 - x0), 6))
            uvs.append(round((y - y0) / float(y1 - y0), 6))
            ws = weight_fn(x, y)
            wx, wy = world_vert(x, y)
            entry = []
            for bone, amt in sorted(ws.items(), key=lambda kv: -kv[1]):
                ox, oy = bone_offset(bone, wx, wy)
                entry.append((BONE_INDEX[bone], ox, oy, amt))
            verts.append(entry)
    tris = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a = j * cols + i
            b = a + 1
            c = a + cols
            dd = c + 1
            tris.extend((a, c, dd, a, dd, b))
    flat = []
    for entry in verts:
        total = sum(e[3] for e in entry) or 1.0
        entry = [e for e in entry if e[3] / total > 0.008][:4]
        total = sum(e[3] for e in entry) or 1.0
        flat.append(len(entry))
        for bone, bx, by, amt in entry:
            flat.extend((bone, round(bx, 3), round(by, 3), round(amt / total, 4)))
    return {"type": "mesh", "uvs": uvs, "triangles": tris, "vertices": flat,
            "width": x1 - x0, "height": y1 - y0}


# ------------------------------------------------------------ weight fns

def w_body(x, y):
    # The painted underlay includes the continuous back hair. Its top edge
    # must follow the head exactly, or any nod opens a horizontal crack.
    if x < 385 or x > 575:
        h = 1.0 - smoothstep(560, 800, y)
        return {"head": h, "root": 1.0 - h}
    if y < 552:
        return {"head": 1.0}
    if y >= 745:
        return {"root": 1.0}
    if y >= 705:
        t = smoothstep(705, 745, y)
        return {"hip": 1.0 - t, "root": t}
    if y >= 645:
        t = smoothstep(645, 705, y)
        return {"spine": 1.0 - t, "hip": t}
    if y >= 592:
        t = smoothstep(592, 645, y)
        return {"chest": 1.0 - t, "spine": t}
    if y >= 552:
        t = smoothstep(552, 592, y)
        return {"neck": 1.0 - t, "chest": t}
    return {"neck": 1.0}


def w_hair(side):
    def f(x, y):
        head = 1.0 - smoothstep(548, 582, y)
        hair = 1.0 - head
        if side == "L":
            t = smoothstep(600, 690, y)
            u = smoothstep(690, 760, y)
        else:
            t = smoothstep(600, 690, y)
            u = smoothstep(690, 760, y)
        out = {}
        if head > 0.001:
            out["head"] = head
        w1 = hair * (1.0 - t)
        w2 = hair * t * (1.0 - u)
        w3 = hair * t * u
        pref = "hairL" if side == "L" else "hairR"
        for name, amt in ((pref + "1", w1), (pref + "2", w2), (pref + "3", w3)):
            if amt > 0.001:
                out[name] = amt
        return out or {"head": 1.0}
    return f


def w_tail(x, y):
    if x <= 625:
        return {"tail1": 1.0}
    if x <= 700:
        t = smoothstep(625, 700, x)
        return {"tail1": 1.0 - t, "tail2": t}
    if x <= 755:
        return {"tail2": 1.0}
    t = smoothstep(755, 800, x)
    return {"tail2": 1.0 - t, "tailFin": t}


def w_skirt(x, y):
    if y <= 630:
        return {"chest": 1.0}
    if y <= 685:
        t = smoothstep(630, 685, y)
        return {"chest": 1.0 - t, "skirt": t}
    return {"skirt": 1.0}


def w_arm_up(side):
    # The inner sleeve seam belongs to the bodice, not the rotating humerus.
    # Blend only the shoulder cap; the elbow and lower sleeve stay rigid.
    b1 = "armL1" if side == "L" else "armR1"

    def f(x, y):
        anchor_x = 414 if side == "L" else 539
        distance = math.hypot(x - anchor_x, y - 566)
        arm = smoothstep(8, 48, distance)
        return {b1: arm, "chest": 1 - arm}
    return f


def w_arm_fore(side):
    b2 = "armL2" if side == "L" else "armR2"

    def f(x, y):
        return {b2: 1.0}
    return f


# ------------------------------------------------------------ animations
# Authored in screen convention: +y is down, +rotation is clockwise on screen.
# mirror_y() converts the channels to Spine's y-up JSON; the runtime flips the
# result back, so what is authored here is what the player sees.

def tr(pairs):
    out = []
    for k in pairs:
        if len(k) == 2:
            t, v = k
            x, y = 0.0, v
        else:
            t, x, y = k
        out.append({"time": round(t, 3), "x": round(x, 3), "y": round(y, 3)})
    return out


def ro(pairs):
    return [{"time": round(t, 3), "value": round(v, 3)} for t, v in pairs]


def ikf(pairs, bend=True):
    """IK constraint timeline frames.  spine-cpp keeps the frames directly under
    the constraint name (no nested "mix" channel).  Each frame also carries its
    own bendPositive, defaulting to TRUE when absent -- the timeline value wins
    over the constraint setup, so the elbow side MUST be repeated here."""
    return [{"time": round(t, 3), "mix": round(m, 3), "bendPositive": bend}
            for t, m in pairs]


def dord(offsets):
    """Draw-order key from "move these slots this far forward" requests.

    spine-cpp's reader does NOT interpret the offsets as moves: it walks the
    slots in setup order, writes each listed slot to `index = i + offset`, and
    then fills every position still empty with the *unlisted* slots in setup
    order.  If two listed slots land on the same index, fewer positions get
    filled than the second pass expects and the reader runs off the end of its
    `unchanged` buffer -- silent memory corruption that segfaults much later,
    in an unrelated clip (that is what killed hop_sit / cheer / stretch).

    So apply the moves here, as moves, and emit the resulting permutation in
    full: every slot listed once, sorted by setup index, targets all distinct.
    """
    order = [name for name, _bone, _att in SLOTS]
    n = len(order)
    seq = list(order)
    for name, off in sorted(offsets, key=lambda kv: order.index(kv[0])):
        i = seq.index(name)
        j = max(0, min(n - 1, i + off))
        seq.pop(i)
        seq.insert(j, name)
    return [{"time": 0.0, "offsets": [
        {"slot": name, "offset": seq.index(name) - order.index(name)}
        for name in order]}]


def col(pairs):
    """Slot colour keys: (time, alpha 0..1) -> RRGGBBAA (white, alpha)."""
    return [{"time": round(t, 3), "color": "ffffff%02x" % int(round(a * 255))}
            for t, a in pairs]


def sc(pairs):
    out = []
    for k in pairs:
        if len(k) == 2:
            t, v = k
            x = y = 1.0 + v
        else:
            t, x, y = k
        out.append({"time": round(t, 3), "x": round(x, 4), "y": round(y, 4)})
    return out


def att(pairs):
    out = []
    for t, n in pairs:
        key = {"time": round(t, 3)}
        if n is not None:
            key["name"] = n
        out.append(key)
    return out


def sine_pairs(T, amp, phase=0.0, base=0.0, n=8):
    return [(T * i / n, base + amp * math.sin(2 * math.pi * i / n + phase))
            for i in range(n + 1)]


IK_KEYS = [("ik_arm_l", True), ("ik_arm_r", False), ("ik_work_l", True),
           ("ik_work_r", False), ("ik_slack_l", True), ("ik_slack_r", False),
           ("s_ik_arm_r", False), ("d_ik_l", True), ("d_ik_r", True)]
SIDE_SLOTS = ("s_hair_back", "s_body", "s_arm_up_l", "s_arm_up_r",
              "s_head", "s_arm_fore_l", "s_arm_fore_r")
# the front set the drink fades out while the side set fades in: body, hair,
# head, both arms and the front-loading duplicates
FRONT_SLOTS = ("hair_back", "hair_l", "hair_r", "body", "skirt", "tail",
               "arm_up_l", "arm_up_r", "arm_fore_l", "arm_fore_r",
               "head", "eyes", "mouth", "hand_l", "hand_r",
               "arm_fore_l_front", "arm_fore_r_front",
               "hand_l_front", "hand_r_front")
PROP_SLOTS = ("water", "cup", "cup_hand_l", "cup_hand_r",
              "book", "pen", "pen_hand", "fish", "fish_hand_l", "fish_hand_r",
              "arm_fore_l_front", "arm_fore_r_front",
              "hand_l_front", "hand_r_front") + SIDE_SLOTS


def ik_reset():
    return {name: ikf([(0, 0.0)], bend) for name, bend in IK_KEYS}


def pose_oneshot(pose, T, out=False, lead=0.18):
    """Turn a held pose into a one-shot entry or exit.

    Every channel is rebuilt from the pose's first key, so entry starts at the
    setup pose and overshoots slightly backwards first (a raise that begins
    with a tiny dip), and exit starts on the pose and settles through it.
    """
    bones = {}
    for bone, chans in pose.items():
        nb = {}
        for kind, keys in chans.items():
            k0 = keys[0]
            if kind == "rotate":
                v = k0["value"]
                if out:
                    nb[kind] = ro([(0, v), (T * 0.7, v * 0.12), (T, 0.0)])
                else:
                    nb[kind] = ro([(0, 0.0), (T * lead, -v * 0.1), (T, v)])
            else:
                x, y = k0.get("x", 0.0), k0.get("y", 0.0)
                if out:
                    nb[kind] = tr([(0, x, y), (T * 0.7, x * 0.2, y * 0.2), (T, 0, 0)])
                else:
                    nb[kind] = tr([(0, 0, 0), (T * lead, -x * 0.1, -y * 0.1), (T, x, y)])
        bones[bone] = nb
    return bones


def arms_front(a, sides="lr"):
    """Route raised forearms and palms through the front slots.

    Cheer, stretch, the alarmed hops and the wave lift the arms past the side
    hair, which lives in the `head` layer; drawn from their normal slots they
    vanish behind it.  Blank the back slot and use its duplicate up front.
    """
    for side, hand in (("l", "hand_l"), ("r", "hand_rest")):
        if side not in sides:
            continue
        fore = "arm_fore_" + side
        a[fore] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
        a[fore + "_front"] = {"attachment": att([(0, fore)]), "rgba": col([(0, 1.0)])}
        a["hand_" + side] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
        a["hand_" + side + "_front"] = {"attachment": att([(0, hand)]),
                                        "rgba": col([(0, 1.0)])}
    return a


def fade_out(a, slots, t0=0.0, t1=0.0):
    """Fade slots to transparent, leaving their attachment alone."""
    for s in slots:
        ch = a.setdefault(s, {})
        ch["rgba"] = col([(0, 0.0)] if t1 == 0.0
                         else [(0, 1.0), (t0, 1.0), (t1, 0.0)])
    return a


def fade_in(a, slots, t0=0.0, t1=0.0, attach=True):
    """Fade slots up.  `attach` is for the side set, whose slots are empty at
    setup and carry the art under their own name; the front slots keep the
    attachment they already have (hand_r is `hand_rest`, eyes is `eyes_open`)."""
    for s in slots:
        ch = a.setdefault(s, {})
        if attach:
            ch["attachment"] = att([(0, s)])
        ch["rgba"] = col([(0, 1.0)] if t1 == 0.0
                         else [(0, 0.0), (t0, 0.0), (t1, 1.0)])
    return a


def base_anim(T, *, eyes, mouth, hand=True):
    """Every looping clip resets the props, the grip hands and the arm IK so
    an interrupted chain cannot leave a bottle or a notebook on screen."""
    a = {"ik": ik_reset()}
    for slot in PROP_SLOTS:
        a[slot] = {"attachment": att([(0, None)]), "rgba": col([(0, 1.0)])}
    if hand:
        a["hand_r"] = {"attachment": att([(0, "hand_rest")]), "rgba": col([(0, 1.0)])}
        a["hand_l"] = {"attachment": att([(0, "hand_l")]), "rgba": col([(0, 1.0)])}
    a["eyes"] = {"attachment": eyes}
    a["mouth"] = {"attachment": mouth}
    # Draw order is stored as offsets on the skeleton and survives a clip
    # change, so every clip restores the setup order at t=0 (offset 0 on all
    # slots).  present then lifts the offered arm above the head on top of it.
    a["drawOrder"] = dord([(name, 0) for name, _bone, _att in SLOTS])
    return a


# a single hop; repeated with an offset for the two-hop reminders
HOP_Y = [(0.00, 0), (0.10, 4), (0.20, -24), (0.32, -30), (0.44, -16),
         (0.54, 0), (0.62, 3), (0.74, 0)]
HOP_SCALE = [(0.00, 1.0, 1.0), (0.10, 1.05, 0.94), (0.24, 0.97, 1.05),
             (0.44, 1.0, 1.02), (0.54, 1.05, 0.94), (0.62, 1.02, 0.98),
             (0.74, 1.0, 1.0)]


def hop_keys(offset=0.0):
    return [(round(t + offset, 3), y) for t, y in HOP_Y]


def hop_scale(offset=0.0):
    return [(round(t + offset, 3), x, y) for t, x, y in HOP_SCALE]


def build_animations():
    anims = {}

    # ---------------------------------------------------------- idle 6 s
    # 左顾右盼: the eyes lead, the head follows ~0.25 s later, hold, return.
    T = 6.0
    a = base_anim(T, eyes=att([(0, "eyes_open"), (0.7, "eyes_left"), (2.0, "eyes_open"),
                               (3.4, "eyes_right"), (4.8, "eyes_open"),
                               (5.3, "eyes_closed"), (5.45, "eyes_open")]),
                  mouth=att([(0, "mouth_default")]))
    a["bones"] = {
        "root": {"translate": tr(sine_pairs(T, 2.0, n=8))},
        "chest": {"scale": sc(sine_pairs(T, 0.006, n=8))},
        "spine": {"rotate": ro([(0, 0), (1.0, -1.2), (2.1, 0), (3.8, 1.2),
                                (4.9, 0), (T, 0)])},
        "neck": {"rotate": ro([(0, 0), (0.95, -2.5), (1.9, 0), (3.65, 2.5),
                               (4.7, 0), (T, 0)])},
        "head": {"translate": tr([(0, 0, 0), (0.95, -7, 0), (1.9, 0, 0),
                                  (3.65, 7, 0), (4.7, 0, 0), (T, 0, 0)]),
                 "rotate": ro([(0, 0), (0.95, -4), (2.0, 0), (3.7, 4),
                               (4.8, 0), (T, 0)])},
        "hairL1": {"rotate": ro(sine_pairs(T, 1.2, 0.9, 0.0, 8))},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.8, 1.4, 0.5, 8))},
        "hairL3": {"rotate": ro(sine_pairs(T, 2.4, 1.9, 1.0, 8))},
        "hairR1": {"rotate": ro(sine_pairs(T, -1.2, 0.7, 0.0, 8))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.8, 1.2, 0.5, 8))},
        "hairR3": {"rotate": ro(sine_pairs(T, -2.4, 1.7, 1.0, 8))},
        "tail1": {"rotate": ro(sine_pairs(T, 2.0, 0.3, 0.0, 8))},
        "tail2": {"rotate": ro(sine_pairs(T, 2.8, 0.8, 0.5, 8))},
        "tailFin": {"rotate": ro(sine_pairs(T, 3.4, 1.3, 1.0, 8))},
        "skirt": {"rotate": ro(sine_pairs(T, 0.8, 0.4, 0.0, 8))},
        "armL1": {"rotate": ro(sine_pairs(T, 0.4, 0.5, 0.0, 8))},
        "armL2": {"rotate": ro(sine_pairs(T, 0.6, 0.9, 0.0, 8))},
        "armR1": {"rotate": ro(sine_pairs(T, -0.4, 0.5, 0.0, 8))},
        "armR2": {"rotate": ro(sine_pairs(T, -0.6, 0.9, 0.0, 8))},
    }
    anims["idle"] = a

    # ------------------------------------------------------- working 4.6 s
    # 抱本子写字: the book rides on its own bone; both wrists are IK'd onto
    # targets parented to the book and the pen, so the pen tip cannot leave the
    # page.  The middle pause is the "thinking" beat.
    T = 4.6
    a = base_anim(T, eyes=att([(0, "eyes_down"), (1.75, "eyes_open"),
                               (2.10, "eyes_down"), (3.95, "eyes_open"),
                               (4.15, "eyes_down")]),
                  mouth=att([(0, "mouth_default")]))
    a["ik"]["ik_work_l"] = ikf([(0, 1.0), (T, 1.0)], bend=True)
    a["ik"]["ik_work_r"] = ikf([(0, 1.0), (T, 1.0)], bend=False)
    a["book"] = {"attachment": att([(0, "book")]), "rgba": col([(0, 1.0)])}
    a["pen"] = {"attachment": att([(0, "pen")]), "rgba": col([(0, 1.0)])}
    # the fist holding the pen is drawn in front of the pad, on the pen bone
    a["pen_hand"] = {"attachment": att([(0, "hand_pen")]), "rgba": col([(0, 1.0)])}
    # the resting mitten would collide with the pen hand
    a["hand_r"] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
    a["bones"] = {
        "root": {"translate": tr(sine_pairs(T, 0.8, n=8))},
        "chest": {"rotate": ro([(0, 1.0), (T, 1.0)])},
        "book": {"rotate": ro([(0, -4), (1.8, -3.2), (3.4, -4), (T, -4)]),
                 "translate": tr([(0, 0, 0), (1.8, 0, 1), (3.4, 0, 0), (T, 0, 0)])},
        "pen": {"translate": tr([
            (0, 0, 0), (0.14, -5, 1), (0.32, 3, -1), (0.52, -4, 1),
            (0.72, 2, 0), (0.92, -5, 1), (1.12, 3, -1), (1.32, -2, 0),
            (1.52, 4, 1), (1.70, 0, 0), (2.30, 0, 0), (2.46, -4, 1),
            (2.66, 3, -1), (2.86, -3, 1), (3.06, 2, 0), (3.26, -4, 1),
            (3.46, 3, 0), (3.66, -1, 0), (3.95, 0, 0), (T, 0, 0)])},
        "head": {"translate": tr([(0, 0, 5), (1.7, 0, 3), (2.1, 0, 5),
                                  (3.9, 0, 1), (4.2, 0, 5), (T, 0, 5)]),
                 "rotate": ro([(0, 3), (1.7, 1), (2.1, 2.2), (3.9, -2),
                               (4.2, 3), (T, 3)])},
        "neck": {"rotate": ro([(0, 2.0), (1.9, 1.5), (3.9, 0.8), (T, 2.0)])},
        "hairL1": {"rotate": ro(sine_pairs(T, 0.7, 0.6, 0.0, 8))},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.1, 1.1, 0.6, 8))},
        "hairL3": {"rotate": ro(sine_pairs(T, 1.6, 1.6, 1.2, 8))},
        "hairR1": {"rotate": ro(sine_pairs(T, -0.7, 0.8, 0.0, 8))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.1, 1.3, 0.6, 8))},
        "hairR3": {"rotate": ro(sine_pairs(T, -1.6, 1.8, 1.2, 8))},
        "tail1": {"rotate": ro(sine_pairs(T, 1.4, 0.3, 0.0, 8))},
        "tail2": {"rotate": ro(sine_pairs(T, 2.0, 0.8, 0.5, 8))},
        "tailFin": {"rotate": ro(sine_pairs(T, 2.6, 1.3, 1.0, 8))},
        "skirt": {"rotate": ro(sine_pairs(T, 0.5, 0.2, 0.0, 8))},
    }
    anims["working"] = a

    # Entry / exit around the writing loop: the pad comes up from the apron in
    # the left hand, the pen and the fist arrive once the pad settles.
    T = 1.0
    a = base_anim(T, eyes=att([(0, "eyes_open"), (0.7, "eyes_down")]),
                  mouth=att([(0, "mouth_default")]))
    a["ik"]["ik_work_l"] = ikf([(0, 0.0), (0.06, 0.0), (0.40, 1.0), (T, 1.0)], True)
    a["ik"]["ik_work_r"] = ikf([(0, 0.0), (0.34, 0.0), (0.56, 1.0), (T, 1.0)], False)
    # the pad only materialises once the left hand has reached it (IK is done
    # at 0.40), so it never floats in the air with her arms still down
    a["book"] = {"attachment": att([(0, "book")]),
                 "rgba": col([(0, 0.0), (0.34, 0.0), (0.48, 1.0)])}
    a["pen"] = {"attachment": att([(0, "pen")]),
                "rgba": col([(0, 0.0), (0.40, 0.0), (0.56, 1.0)])}
    a["pen_hand"] = {"attachment": att([(0, "hand_pen")]),
                     "rgba": col([(0, 0.0), (0.40, 0.0), (0.56, 1.0)])}
    a["hand_r"] = {"attachment": att([(0, "hand_rest"), (0.40, "")]),
                   "rgba": col([(0, 1.0), (0.28, 1.0), (0.40, 0.0)])}
    a["bones"] = {
        "book": {"translate": tr([(0, 0, 34), (0.36, 0, 32), (0.72, 0, 0),
                                  (T, 0, 0)]),
                 "rotate": ro([(0, 0), (0.72, -4), (T, -4)])},
        "head": {"translate": tr([(0, 0, 0), (0.72, 0, 5), (T, 0, 5)]),
                 "rotate": ro([(0, 0), (0.72, 3), (T, 3)])},
        "neck": {"rotate": ro([(0, 0), (0.72, 2), (T, 2)])},
        "chest": {"rotate": ro([(0, 0), (0.72, 1), (T, 1)])},
        "hairL2": {"rotate": ro([(0, 0), (0.72, 2), (T, 2)])},
        "hairL3": {"rotate": ro([(0, 0), (0.72, 3), (T, 3)])},
        "hairR2": {"rotate": ro([(0, 0), (0.72, -2), (T, -2)])},
        "hairR3": {"rotate": ro([(0, 0), (0.72, -3), (T, -3)])},
    }
    anims["working_in"] = a

    T = 0.9
    a = base_anim(T, eyes=att([(0, "eyes_down"), (0.4, "eyes_open")]),
                  mouth=att([(0, "mouth_default")]))
    a["ik"]["ik_work_l"] = ikf([(0, 1.0), (0.74, 0.0), (T, 0.0)], True)
    a["ik"]["ik_work_r"] = ikf([(0, 1.0), (0.20, 0.0), (T, 0.0)], False)
    a["book"] = {"attachment": att([(0, "book")]),
                 "rgba": col([(0, 1.0), (0.54, 1.0), (0.72, 0.0)])}
    a["pen"] = {"attachment": att([(0, "pen")]),
                "rgba": col([(0, 1.0), (0.16, 0.0)])}
    a["pen_hand"] = {"attachment": att([(0, "hand_pen")]),
                     "rgba": col([(0, 1.0), (0.16, 0.0)])}
    a["hand_r"] = {"attachment": att([(0, ""), (0.18, "hand_rest")]),
                   "rgba": col([(0, 0.0), (0.18, 0.0), (0.32, 1.0)])}
    a["bones"] = {
        "book": {"translate": tr([(0, 0, 0), (0.34, 0, 2), (0.70, 0, 34),
                                  (T, 0, 34)]),
                 "rotate": ro([(0, -4), (0.4, 0), (T, 0)])},
        "head": {"translate": tr([(0, 0, 5), (0.5, 0, 0), (T, 0, 0)]),
                 "rotate": ro([(0, 3), (0.5, 0), (T, 0)])},
        "neck": {"rotate": ro([(0, 2), (0.5, 0), (T, 0)])},
        "chest": {"rotate": ro([(0, 1), (0.5, 0), (T, 0)])},
        "hairL2": {"rotate": ro([(0, 2), (0.6, 0), (T, 0)])},
        "hairL3": {"rotate": ro([(0, 3), (0.6, 0), (T, 0)])},
        "hairR2": {"rotate": ro([(0, -2), (0.6, 0), (T, 0)])},
        "hairR3": {"rotate": ro([(0, -3), (0.6, 0), (T, 0)])},
    }
    anims["working_out"] = a

    # --------------------------------------------------------- slack 6 s
    # 抱鲸鱼抚摸: one whole whale prop on the `fish` bone; the right hand's IK
    # target slides along its back while the left palm cradles the belly.
    T = 6.0
    a = base_anim(T, eyes=att([(0, "eyes_half"), (3.3, "eyes_closed"),
                               (3.7, "eyes_half")]),
                  mouth=att([(0, "mouth_smile")]))
    a["ik"]["ik_slack_l"] = ikf([(0, 1.0), (T, 1.0)], bend=True)
    a["ik"]["ik_slack_r"] = ikf([(0, 1.0), (T, 1.0)], bend=False)
    a["fish"] = {"attachment": att([(0, "fish")]), "rgba": col([(0, 1.0)])}
    # The stroking arm is short here (it only has to clear the plush's back
    # from her shoulder), so bringing *its* forearm forward shows the sleeve
    # that connects the hand to her, without burying the whale.  The far
    # forearm stays behind it -- in front it hid half the plush.
    arms_front(a, "r")
    a["hand_r_front"] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
    a["fish_hand_l"] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
    a["fish_hand_r"] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
    a["fish_hand_l_front"] = {"attachment": att([(0, "fish_hand_l")]),
                              "rgba": col([(0, 1.0)])}
    a["fish_hand_r_front"] = {"attachment": att([(0, "fish_hand_r")]),
                              "rgba": col([(0, 1.0)])}
    a["hand_l"] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
    a["hand_r"] = {"attachment": att([(0, "")]), "rgba": col([(0, 1.0)])}
    # no drawOrder here: the fish slot already sits in front of the forearms.
    # Lifting the sleeves over it (the old +5) buried most of the whale.
    a["bones"] = {
        "root": {"translate": tr(sine_pairs(T, 2.6, n=6))},
        "chest": {"scale": sc(sine_pairs(T, 0.010, n=6))},
        "spine": {"rotate": ro([(0, 1.0), (3.0, -0.5), (T, 1.0)])},
        "neck": {"rotate": ro([(0, 1.5), (3.0, 2.5), (T, 1.5)])},
        "head": {"rotate": ro([(0, 3.0), (3.0, 5.0), (T, 3.0)]),
                 "translate": tr([(0, 0, 2), (3.0, 1, 3), (T, 0, 2)])},
        "fish": {"translate": tr([(0, 0, 0), (1.5, 0, -2), (3.0, 0, 0),
                                  (4.5, 0, -2), (T, 0, 0)]),
                 "rotate": ro([(0, 0), (3.0, 1.5), (T, 0)])},
        # the petting hand lies along the whale's back and strokes it: one slow
        # pass each way, lengthened for the bigger plush so the hand travels
        # along the back instead of trembling in one spot
        "slackR": {"translate": tr([(0, 0, 0), (0.9, -13, 1), (2.1, 13, -1),
                                    (3.3, -14, 1), (4.5, 13, -1), (5.6, -5, 0),
                                    (T, 0, 0)]),
                   "rotate": ro([(0, 10), (0.9, 14), (2.1, 6),
                                 (3.3, 14), (4.5, 6), (5.6, 11), (T, 10)])},
        # the cradling palm takes the whale's weight: a slow lift and settle
        "slackL": {"translate": tr([(0, 0, 0), (3.0, 1, 1), (T, 0, 0)]),
                   "rotate": ro([(0, -6), (3.0, -2), (T, -6)])},
        "hairL1": {"rotate": ro(sine_pairs(T, 1.4, 0.8, 1.0, 6))},
        "hairL2": {"rotate": ro(sine_pairs(T, 2.2, 1.3, 2.0, 6))},
        "hairL3": {"rotate": ro(sine_pairs(T, 3.0, 1.8, 3.0, 6))},
        "hairR1": {"rotate": ro(sine_pairs(T, -1.4, 0.6, -1.0, 6))},
        "hairR2": {"rotate": ro(sine_pairs(T, -2.2, 1.1, -2.0, 6))},
        "hairR3": {"rotate": ro(sine_pairs(T, -3.0, 1.6, -3.0, 6))},
        "tail1": {"rotate": ro(sine_pairs(T, 2.4, 0.4, 0.0, 6))},
        "tail2": {"rotate": ro(sine_pairs(T, 3.2, 0.9, 0.0, 6))},
        "tailFin": {"rotate": ro(sine_pairs(T, 4.0, 1.4, 0.0, 6))},
        "skirt": {"rotate": ro(sine_pairs(T, 1.0, 0.5, 0.0, 6))},
    }
    anims["slack"] = a

    # Entry / exit around the hug.  pet.gd plays in -> slack -> out, so the
    # whale is taken out of the apron and put back instead of appearing at full
    # size in mid air.  The whale rises first, her own arms follow it up, and
    # the mittens are swapped for the hugging hands in a single frame once the
    # wrists have actually arrived (S) -- cross-fading them showed four hands.
    T = 1.1
    S = 0.66
    a = base_anim(T, eyes=att([(0, "eyes_open"), (0.5, "eyes_half")]),
                  mouth=att([(0, "mouth_default"), (0.6, "mouth_smile")]))
    a["ik"]["ik_slack_l"] = ikf([(0, 0.0), (0.30, 0.0), (S, 1.0), (T, 1.0)], True)
    a["ik"]["ik_slack_r"] = ikf([(0, 0.0), (0.30, 0.0), (S, 1.0), (T, 1.0)], False)
    a["fish"] = {"attachment": att([(0, "fish")]),
                 "rgba": col([(0, 0.0), (0.10, 0.0), (0.34, 1.0)])}
    a["fish_hand_l"] = {"attachment": att([(0, "fish_hand_l")]),
                        "rgba": col([(0, 0.0), (S - 0.001, 0.0), (S, 1.0)])}
    a["fish_hand_r"] = {"attachment": att([(0, "fish_hand_r")]),
                        "rgba": col([(0, 0.0), (S - 0.001, 0.0), (S, 1.0)])}
    a["hand_l"] = {"attachment": att([(0, "hand_l"), (S, "")]),
                   "rgba": col([(0, 1.0), (S - 0.001, 1.0), (S, 0.0)])}
    a["hand_r"] = {"attachment": att([(0, "hand_rest"), (S, "")]),
                   "rgba": col([(0, 1.0), (S - 0.001, 1.0), (S, 0.0)])}
    a["bones"] = {
        # it comes up out of the apron over half a second; IK only starts once
        # it is high enough for the hands to reach (the arm chain is 113 px)
        "fish": {"translate": tr([(0, 0, 44), (0.20, 0, 40), (0.60, 0, 0),
                                  (T, 0, 0)])},
        "head": {"rotate": ro([(0, 0), (0.7, 2.5), (T, 2.5)]),
                 "translate": tr([(0, 0, 0), (0.7, 0, 2), (T, 0, 2)])},
        "chest": {"scale": sc([(0, 1, 1), (0.74, 1.01, 1.01), (T, 1.01, 1.01)])},
        "hairL2": {"rotate": ro([(0, 0), (0.74, 2.5), (T, 2.5)])},
        "hairL3": {"rotate": ro([(0, 0), (0.74, 3.5), (T, 3.5)])},
        "hairR2": {"rotate": ro([(0, 0), (0.74, -2.5), (T, -2.5)])},
        "hairR3": {"rotate": ro([(0, 0), (0.74, -3.5), (T, -3.5)])},
    }
    anims["slack_in"] = a

    T = 1.0
    S = 0.30
    a = base_anim(T, eyes=att([(0, "eyes_half"), (0.35, "eyes_open")]),
                  mouth=att([(0, "mouth_smile"), (0.35, "mouth_default")]))
    a["ik"]["ik_slack_l"] = ikf([(0, 1.0), (0.36, 1.0), (0.92, 0.0), (T, 0.0)], True)
    a["ik"]["ik_slack_r"] = ikf([(0, 1.0), (0.36, 1.0), (0.92, 0.0), (T, 0.0)], False)
    a["fish"] = {"attachment": att([(0, "fish")]),
                 "rgba": col([(0, 1.0), (0.52, 1.0), (0.80, 0.0)])}
    # the same one-frame swap back to her mittens, while the arms still hold
    # the whale; then the plush is lowered and fades into the apron
    a["fish_hand_l"] = {"attachment": att([(0, "fish_hand_l")]),
                        "rgba": col([(0, 1.0), (S - 0.001, 1.0), (S, 0.0)])}
    a["fish_hand_r"] = {"attachment": att([(0, "fish_hand_r")]),
                        "rgba": col([(0, 1.0), (S - 0.001, 1.0), (S, 0.0)])}
    a["hand_l"] = {"attachment": att([(0, ""), (S, "hand_l")]),
                   "rgba": col([(0, 0.0), (S - 0.001, 0.0), (S, 1.0)])}
    a["hand_r"] = {"attachment": att([(0, ""), (S, "hand_rest")]),
                   "rgba": col([(0, 0.0), (S - 0.001, 0.0), (S, 1.0)])}
    a["bones"] = {
        "fish": {"translate": tr([(0, 0, 0), (0.40, 0, 4), (0.90, 0, 36),
                                  (T, 0, 36)])},
        "head": {"rotate": ro([(0, 2.5), (0.4, 0), (T, 0)])},
        "hairL2": {"rotate": ro([(0, 2.5), (0.5, 0), (T, 0)])},
        "hairL3": {"rotate": ro([(0, 3.5), (0.5, 0), (T, 0)])},
        "hairR2": {"rotate": ro([(0, -2.5), (0.5, 0), (T, 0)])},
        "hairR3": {"rotate": ro([(0, -3.5), (0.5, 0), (T, 0)])},
    }
    anims["slack_out"] = a

    # -------------------------------------------------- present panel 3 s
    # Right-click / settings open: turn toward the panel on the character's
    # right and offer it with an open palm.  Loops while a panel is up.
    T = 3.0
    a = base_anim(T, eyes=att([(0, "eyes_right")]),
                  mouth=att([(0, "mouth_smile")]))
    # the forearm goes to the front slot WITH the palm: lifting only the hand
    # left the cuff and the sleeve behind the side hair while the hand floated
    # in front of it
    # Only the near arm comes forward: the far arm keeps its own sleeve and its
    # resting hand.  "lr" here would blank the far sleeve and leave a floating
    # hand, and the reference for this pose has one hand offering, not two.
    arms_front(a, "r")
    a["hand_r_front"] = {"attachment": att([(0, "hand_open")]),
                         "rgba": col([(0, 1.0)])}
    present_pose = {
        # a small lean toward the panel, pivoting at the feet
        "root": {"translate": tr(sine_pairs(T, 1.3, n=6)),
                 "rotate": ro([(0, 6.0), (1.5, 6.8), (T, 6.0)])},
        "spine": {"rotate": ro([(0, 3.0), (1.5, 3.6), (T, 3.0)])},
        "chest": {"rotate": ro([(0, 3.0), (1.5, 3.6), (T, 3.0)])},
        "neck": {"rotate": ro([(0, 2.0), (1.5, 2.6), (T, 2.0)])},
        "head": {"translate": tr([(0, 7, 0), (1.5, 8, -1), (T, 7, 0)]),
                 "rotate": ro([(0, 4), (1.5, 5), (T, 4)])},
        # The near arm offers the panel: the elbow drops to the waist and only
        # the forearm comes up, so the wrist lands at about -16 deg -- palm up,
        # fingers toward the panel, thumb on top.  armR1/armR2 carry the
        # offering; handR trims the wrist so the painted palm is not left
        # angled at the ceiling.
        "armR1": {"rotate": ro([(0, -16), (0.9, -20), (1.8, -12), (T, -16)])},
        "armR2": {"rotate": ro([(0, -57), (0.9, -60), (1.8, -53), (T, -57)])},
        "handR": {"rotate": ro([(0, 6), (0.9, 2), (1.8, 10), (T, 6)])},
        # the far arm just hangs; a few degrees of swing keeps it alive
        "armL1": {"rotate": ro(sine_pairs(T, 1.2, 0.6, 0.0, 4))},
        "armL2": {"rotate": ro(sine_pairs(T, 1.8, 0.8, 0.3, 3))},
        "hairL1": {"rotate": ro(sine_pairs(T, 0.9, 0.8, 0.0, 6))},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.4, 1.3, 0.4, 6))},
        "hairL3": {"rotate": ro(sine_pairs(T, 2.0, 1.8, 0.8, 6))},
        "hairR1": {"rotate": ro(sine_pairs(T, -0.9, 0.6, 0.0, 6))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.4, 1.1, 0.4, 6))},
        "hairR3": {"rotate": ro(sine_pairs(T, -2.0, 1.6, 0.8, 6))},
        "tail1": {"rotate": ro(sine_pairs(T, 1.8, 0.3, 0.0, 6))},
        "tail2": {"rotate": ro(sine_pairs(T, 2.4, 0.8, 0.4, 6))},
        "tailFin": {"rotate": ro(sine_pairs(T, 3.0, 1.3, 0.8, 6))},
    }
    a["bones"] = present_pose
    anims["present"] = a

    # Entry / exit around the held offer.  Looping the hold alone meant the
    # hand appeared already raised (and vanished when the card closed); these
    # two one-shots raise and lower it.  pet.gd plays in -> hold -> out.
    def present_oneshot(pose, T, out, both):
        b = base_anim(T, eyes=att([(0, "eyes_open"), (0.25, "eyes_right")] if not out
                                  else [(0, "eyes_right"), (0.3, "eyes_open")]),
                      mouth=att([(0, "mouth_default"), (0.3, "mouth_smile")] if not out
                                else [(0, "mouth_smile"), (0.3, "mouth_default")]))
        arms_front(b, "lr" if both else "r")
        b["hand_r_front"] = {"attachment": att([(0, "hand_open")]),
                             "rgba": col([(0, 1.0)])}
        if both:
            b["hand_l_front"] = {"attachment": att([(0, "hand_open_l")]),
                                 "rgba": col([(0, 1.0)])}
        b["bones"] = pose_oneshot(pose, T, out)
        return b

    anims["present_in"] = present_oneshot(present_pose, 0.55, False, False)
    anims["present_out"] = present_oneshot(present_pose, 0.45, True, False)

    # ------------------------------------- present2: chest, then invitation, 3 s
    # The alternate panel pose, from the guide's third reference: one hand comes
    # to rest over the chest, then the other opens toward the cards.  Distinct
    # from `present`, which offers with a single hand and nothing else -- two
    # palms spread at once was the pose the guide explicitly ruled out.
    T = 3.0
    a = base_anim(T, eyes=att([(0, "eyes_right")]),
                  mouth=att([(0, "mouth_smile")]))
    # both forearms ride in front of the head with their palms: the chest hand
    # sits over the apron and the offering hand crosses the side hair, so both
    # sleeves have to leave their normal slots or the hair covers them
    arms_front(a, "lr")
    a["hand_r_front"] = {"attachment": att([(0, "hand_open")]),
                         "rgba": col([(0, 1.0)])}
    a["hand_l_front"] = {"attachment": att([(0, "hand_open_l")]),
                         "rgba": col([(0, 1.0)])}
    present2_pose = {
        # the whole body pivots toward the cards, feet planted, so she is seen
        # from the side rather than squared up to the viewer
        "root": {"translate": tr([(0, 6, 0), (1.5, 7, 0), (T, 6, 0)]),
                 "rotate": ro([(0, 10.0), (1.5, 11.0), (T, 10.0)])},
        "spine": {"rotate": ro([(0, 4.0), (1.5, 4.6), (T, 4.0)])},
        "chest": {"rotate": ro([(0, 4.0), (1.5, 4.6), (T, 4.0)])},
        "neck": {"rotate": ro([(0, 2.0), (1.5, 2.6), (T, 2.0)])},
        "head": {"translate": tr([(0, 8, 0), (1.5, 9, -1), (T, 8, 0)]),
                 "rotate": ro([(0, 4), (1.5, 5), (T, 4)])},
        # far arm: folds across until the palm rests on the apron bib.  Solved
        # as a two-bone reach to a wrist at (450, 632): the elbow drops to the
        # waist (62.2 deg) and the forearm comes back down-right (17.3 deg), so
        # the elbow stays under the hand instead of flaring out sideways.
        "armL1": {"rotate": ro([(0, -38), (0.9, -41), (1.8, -35), (T, -38)])},
        "armL2": {"rotate": ro([(0, -68), (0.9, -71), (1.8, -65), (T, -68)])},
        "handL": {"rotate": ro([(0, -50), (0.9, -54), (1.8, -46), (T, -50)])},
        # near arm: the same offer as `present`, a touch lower and softer
        "armR1": {"rotate": ro([(0, -14), (0.9, -18), (1.8, -10), (T, -14)])},
        "armR2": {"rotate": ro([(0, -52), (0.9, -55), (1.8, -48), (T, -52)])},
        "handR": {"rotate": ro([(0, 4), (0.9, 0), (1.8, 8), (T, 4)])},
        "hairL1": {"rotate": ro(sine_pairs(T, 0.9, 0.8, 0.0, 6))},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.4, 1.3, 0.4, 6))},
        "hairL3": {"rotate": ro(sine_pairs(T, 2.0, 1.8, 0.8, 6))},
        "hairR1": {"rotate": ro(sine_pairs(T, -0.9, 0.6, 0.0, 6))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.4, 1.1, 0.4, 6))},
        "hairR3": {"rotate": ro(sine_pairs(T, -2.0, 1.6, 0.8, 6))},
        "tail1": {"rotate": ro(sine_pairs(T, 1.8, 0.3, 0.0, 6))},
        "tail2": {"rotate": ro(sine_pairs(T, 2.4, 0.8, 0.4, 6))},
        "tailFin": {"rotate": ro(sine_pairs(T, 3.0, 1.3, 0.8, 6))},
    }
    a["bones"] = present2_pose
    anims["present2"] = a

    # both=True: present2 raises BOTH arms in front, so its entry and exit have
    # to route both sleeves forward too -- with only the near one the chest
    # hand's cuff stayed in the back slot and the palm hung in the hair
    anims["present2_in"] = present_oneshot(present2_pose, 0.6, False, True)
    anims["present2_out"] = present_oneshot(present2_pose, 0.5, True, True)

    # ---------------------------------------------------- needs_input 3 s
    # Waiting for you: she is *quiet*.  The hop that announces the state is a
    # separate one-shot (needs_input_hop, played once when the state starts),
    # because this clip loops -- a hop in here meant she jumped every 3 s for
    # as long as the prompt stayed open.  What is left is a small hand raise,
    # a tilted head and a blink, then stillness.
    T = 3.0
    a = base_anim(T, eyes=att([(0, "eyes_open"), (1.9, "eyes_half"),
                               (2.05, "eyes_open"), (T, "eyes_open")]),
                  mouth=att([(0, "mouth_default"), (1.5, "mouth_smile"),
                             (2.4, "mouth_default")]))
    arms_front(a, "l")
    a["bones"] = {
        "root": {"translate": tr(sine_pairs(T, 2.0, n=6))},
        "chest": {"scale": sc(sine_pairs(T, 0.005, n=6))},
        "head": {"rotate": ro([(0, 3.0), (1.4, 4.5), (2.6, 3.0), (T, 3.0)]),
                 "translate": tr([(0, -2, 0), (T, -2, 0)])},
        "neck": {"rotate": ro([(0, 1.0), (T, 1.0)])},
        # the announcement (a hop and a real wave) is the one-shot; in the
        # loop the hand only lifts a little off the waist and settles, so a
        # long wait looks attentive rather than like a stuck animation
        "armL1": {"rotate": ro([(0, 4), (0.45, 24), (1.2, 24),
                                (1.6, 4), (T, 4)])},
        "armL2": {"rotate": ro([(0, 0), (0.45, 14), (0.7, 22), (0.95, 14),
                                (1.2, 20), (1.6, 0), (T, 0)])},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.5, 1.0))},
        "hairL3": {"rotate": ro(sine_pairs(T, 2.0, 1.5))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.2, 0.8))},
        "hairR3": {"rotate": ro(sine_pairs(T, -1.6, 1.3))},
        "tail2": {"rotate": ro(sine_pairs(T, 2.0, 0.6))},
        "tailFin": {"rotate": ro(sine_pairs(T, 2.6, 1.0))},
    }
    a["drawOrder"] = dord([("arm_up_l", 5), ("arm_fore_l", 4), ("hand_l", 4)])
    anims["needs_input"] = a

    # ------------------------------------------ needs_input_hop 1.3 s, once
    # Played by _set_state when the session starts waiting: one hop of
    # "hey, over here", landing into the exact pose the quiet loop starts on.
    T = 1.3
    a = base_anim(T, eyes=att([(0, "eyes_open"), (0.45, "eyes_happy"),
                               (0.95, "eyes_open")]),
                  mouth=att([(0, "mouth_default"), (0.45, "mouth_smile"),
                             (0.95, "mouth_default")]))
    arms_front(a, "l")
    a["bones"] = {
        "root": {"translate": tr(hop_keys(0.0) + [(T, 0)]),
                 "scale": sc(hop_scale(0.0) + [(T, 1, 1)])},
        "head": {"rotate": ro([(0, 3), (0.2, -2), (0.5, 4.5), (0.9, 3), (T, 3)]),
                 "translate": tr([(0, -2, 0), (T, -2, 0)])},
        "neck": {"rotate": ro([(0, 1.0), (T, 1.0)])},
        # the wave: the hand comes up beside her face with the hop and waves
        # twice, then drops to the exact pose the quiet loop starts on
        "armL1": {"rotate": ro([(0, 0), (0.32, 88), (0.62, 86), (0.95, 30),
                                (T, 4)])},
        "armL2": {"rotate": ro([(0, 0), (0.32, 26), (0.5, 6), (0.68, 30),
                                (0.86, 12), (T, 0)])},
        "hairL2": {"rotate": ro([(0, 0), (0.3, 7), (0.56, -5), (0.96, 0), (T, 0)])},
        "hairL3": {"rotate": ro([(0, 0), (0.36, 10), (0.62, -7), (1.02, 0), (T, 0)])},
        "hairR2": {"rotate": ro([(0, 0), (0.3, -7), (0.56, 5), (0.96, 0), (T, 0)])},
        "hairR3": {"rotate": ro([(0, 0), (0.36, -10), (0.62, 7), (1.02, 0), (T, 0)])},
        "tail2": {"rotate": ro([(0, 0), (0.34, 9), (0.6, -6), (1.0, 0), (T, 0)])},
        "tailFin": {"rotate": ro([(0, 0), (0.4, 12), (0.66, -8), (1.06, 0), (T, 0)])},
    }
    anims["needs_input_hop"] = a

    # -------------------------------------------------------- done 1.4 s
    T = 1.4
    a = base_anim(T, eyes=att([(0, "eyes_happy"), (1.15, "eyes_open")]),
                  mouth=att([(0, "mouth_smile"), (1.15, "mouth_default")]))
    a["bones"] = {
        "root": {"translate": tr([(0, 0, 0), (0.22, 0, -12), (0.48, 0, 0),
                                  (0.66, 0, -5), (0.9, 0, 0), (T, 0, 0)])},
        "head": {"rotate": ro([(0, 2), (0.25, 0), (0.6, 2), (T, 2)])},
        "hairL1": {"rotate": ro(sine_pairs(T, 1.6, 0.5))},
        "hairL2": {"rotate": ro(sine_pairs(T, 2.4, 1.0))},
        "hairL3": {"rotate": ro(sine_pairs(T, 3.2, 1.5))},
        "hairR1": {"rotate": ro(sine_pairs(T, -1.6, 0.5))},
        "hairR2": {"rotate": ro(sine_pairs(T, -2.4, 1.0))},
        "hairR3": {"rotate": ro(sine_pairs(T, -3.2, 1.5))},
        "tail1": {"rotate": ro(sine_pairs(T, 2.4, 0.2))},
        "tail2": {"rotate": ro(sine_pairs(T, 3.2, 0.7))},
        "tailFin": {"rotate": ro(sine_pairs(T, 4.0, 1.2))},
    }
    anims["done"] = a

    # ------------------------------------------------------- cheer 1.6 s
    T = 1.6
    a = base_anim(T, eyes=att([(0, "eyes_happy"), (1.35, "eyes_open")]),
                  mouth=att([(0, "mouth_smile"), (1.35, "mouth_default")]))
    a["bones"] = {
        "root": {"translate": tr([(0, 0, 0), (0.25, 0, -16), (0.55, 0, 0), (T, 0, 0)])},
        "head": {"rotate": ro([(0, 0), (0.3, -3), (0.8, 2), (T, 0)])},
        # both hands up beside the face, bouncing -- a "yay" rather than the
        # wide open arms of the stretch, so the two never read alike
        "armL1": {"rotate": ro([(0, 0), (0.3, 96), (0.7, 102), (1.1, 92), (T, 0)])},
        "armL2": {"rotate": ro([(0, 0), (0.3, 28), (0.7, 22), (1.1, 30), (T, 0)])},
        "armR1": {"rotate": ro([(0, 0), (0.3, -96), (0.7, -102), (1.1, -92), (T, 0)])},
        "armR2": {"rotate": ro([(0, 0), (0.3, -28), (0.7, -22), (1.1, -30), (T, 0)])},
        "hairL2": {"rotate": ro(sine_pairs(T, 2.0, 0.8))},
        "hairL3": {"rotate": ro(sine_pairs(T, 2.8, 1.3))},
        "hairR2": {"rotate": ro(sine_pairs(T, -2.0, 0.8))},
        "hairR3": {"rotate": ro(sine_pairs(T, -2.8, 1.3))},
        "tail1": {"rotate": ro(sine_pairs(T, 3.0, 0.3))},
        "tail2": {"rotate": ro(sine_pairs(T, 4.0, 0.8))},
        "tailFin": {"rotate": ro(sine_pairs(T, 5.0, 1.3))},
    }
    arms_front(a)
    anims["cheer"] = a

    # ----------------------------------------------------- stretch 2.8 s
    T = 2.8
    a = base_anim(T, eyes=att([(0, "eyes_open"), (0.35, "eyes_closed"),
                               (2.35, "eyes_open")]),
                  mouth=att([(0, "mouth_default")]))
    a["bones"] = {
        "root": {"translate": tr([(0, 0, 0), (0.9, 0, -7), (1.6, 0, -8),
                                  (2.4, 0, 0), (T, 0, 0)])},
        "chest": {"scale": sc([(0, 1.0, 1.0), (1.2, 1.02, 1.02), (2.0, 1.0, 1.0), (T, 1, 1)])},
        "head": {"rotate": ro([(0, 0), (0.8, -5), (1.8, -6), (2.4, 0), (T, 0)])},
        # arms open wide and *out*, not up: the rig tops out with the hands at
        # ear height, exactly where the white hair wings sit, so a raised
        # stretch vanished into them.  Wide + head back + eyes shut reads as
        # the stretch at any size.
        "armL1": {"rotate": ro([(0, 0), (0.8, 70), (1.8, 78), (2.4, 20), (T, 0)])},
        "armL2": {"rotate": ro([(0, 0), (0.8, 42), (1.8, 50), (2.4, 8), (T, 0)])},
        "armR1": {"rotate": ro([(0, 0), (0.8, -70), (1.8, -78), (2.4, -20), (T, 0)])},
        "armR2": {"rotate": ro([(0, 0), (0.8, -42), (1.8, -50), (2.4, -8), (T, 0)])},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.6, 1.0))},
        "hairL3": {"rotate": ro(sine_pairs(T, 2.2, 1.5))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.6, 1.0))},
        "hairR3": {"rotate": ro(sine_pairs(T, -2.2, 1.5))},
        "tail1": {"rotate": ro(sine_pairs(T, 2.0, 0.3))},
        "tailFin": {"rotate": ro(sine_pairs(T, 3.0, 1.0))},
    }
    arms_front(a)
    anims["stretch"] = a

    # ------------------------------------------------- reminder hops
    # Three different reminders used to be the same clip twice plus a third
    # that only differed by a head tilt, so at desktop size they read as "she
    # jumps again".  Each now has its own rhythm, silhouette and landing:
    #   sit    two small hops, arms out; ends standing with a stretch
    #   alarm  one big, fast startle hop, both hands up by the face, then a
    #          head shake; the only one with a snap
    #   memo   no hop at all: hand to the cheek, head tilt, one nod
    # None loops -- pet.gd plays each once, then the session state resumes.

    def jump_trail(b, T, amp=1.0, hop_at=0.0, n=6):
        """Hair and tail trail the hop and settle a beat after it."""
        for name, a in (("hairL1", 4), ("hairL2", 7), ("hairL3", 10),
                        ("hairR1", -4), ("hairR2", -7), ("hairR3", -10),
                        ("tail1", 6), ("tail2", 9), ("tailFin", 12)):
            keys = []
            for i, t in enumerate((0.0, 0.24, 0.5, 0.9, 1.14, 1.4, 1.8)):
                if t + hop_at > T - 0.01:
                    break
                v = (0, a * 0.7, -a * 0.5, 0, a * 0.6, -a * 0.4, 0)[i]
                keys.append((round(t + hop_at, 3), round(v * amp, 2)))
            keys.append((T, 0))
            b["bones"][name] = {"rotate": ro(keys)}

    # -------------------------------------------------------- hop_sit 3.0 s
    # "起来动动": two light hops with the arms swinging out, then she plants
    # her feet and opens both arms wide, head back, eyes shut -- the sit
    # reminder ends on the stretch she wants you to take.
    T = 3.0
    b = base_anim(T, eyes=att([(0, "eyes_open"), (0.9, "eyes_happy"),
                               (2.15, "eyes_closed"), (2.6, "eyes_open")]),
                  mouth=att([(0, "mouth_smile"), (2.5, "mouth_default")]))
    arms_front(b)
    b["bones"] = {
        "root": {"translate": tr(hop_keys(0.0) + hop_keys(0.9) + [(T, 0)]),
                 "scale": sc(hop_scale(0.0) + hop_scale(0.9) + [(T, 1, 1)])},
        "head": {"rotate": ro([(0, 2), (0.2, -4), (0.45, 3), (0.9, 2),
                               (1.2, -3), (1.7, 3), (2.2, -6), (2.7, 2),
                               (T, 2)]),
                 "translate": tr([(0, 0, 0), (2.15, 0, -3), (2.7, 0, 0),
                                  (T, 0, 0)])},
        "chest": {"scale": sc([(0, 1, 1), (2.15, 1.0, 1.03), (2.7, 1, 1),
                               (T, 1, 1)])},
        "armL1": {"rotate": ro([(0, 0), (0.4, 58), (0.9, 66), (1.4, 54),
                                (2.05, 62), (2.2, 78), (2.6, 82),
                                (2.85, 16), (T, 0)])},
        "armL2": {"rotate": ro([(0, 0), (0.4, 26), (0.9, 34), (1.4, 24),
                                (2.05, 30), (2.2, 46), (2.6, 52),
                                (2.85, 8), (T, 0)])},
        "armR1": {"rotate": ro([(0, 0), (0.4, -58), (0.9, -66), (1.4, -54),
                                (2.05, -62), (2.2, -78), (2.6, -82),
                                (2.85, -16), (T, 0)])},
        "armR2": {"rotate": ro([(0, 0), (0.4, -26), (0.9, -34), (1.4, -24),
                                (2.05, -30), (2.2, -46), (2.6, -52),
                                (2.85, -8), (T, 0)])},
        "skirt": {"rotate": ro([(0, 0), (0.3, 3), (0.6, -2), (1.0, 0),
                                (1.24, 3), (1.5, -2), (T, 0)])},
    }
    jump_trail(b, T)
    anims["hop_sit"] = b

    # ------------------------------------------------------ hop_alarm 1.6 s
    # 闹钟: one big jump, both hands snap up beside the face, then she looks
    # around -- head shakes left and right twice.  Faster and higher than the
    # sit hops, and it is the only clip that snaps.
    T = 1.6
    b = base_anim(T, eyes=att([(0, "eyes_open"), (0.08, "eyes_up"),
                               (0.35, "eyes_open"), (1.3, "eyes_open")]),
                  mouth=att([(0, "mouth_default")]))
    arms_front(b)
    b["bones"] = {
        "root": {"translate": tr([(0, 0, 0), (0.06, 0, 6), (0.14, 0, -30),
                                  (0.26, 0, -44), (0.38, 0, -38), (0.5, 0, -8),
                                  (0.58, 0, 4), (0.7, 0, 0), (T, 0, 0)]),
                 "scale": sc([(0, 1.0, 1.0), (0.06, 1.06, 0.92),
                              (0.2, 0.97, 1.06), (0.38, 1.0, 1.04),
                              (0.5, 1.06, 0.94), (0.6, 1.0, 1.0), (T, 1, 1)])},
        "head": {"rotate": ro([(0, 0), (0.08, -9), (0.32, -4), (0.52, 7),
                               (0.7, -6), (0.88, 5), (1.05, -4), (1.25, 1),
                               (T, 0)]),
                 "translate": tr([(0, 0, 0), (0.08, 0, -3), (0.4, 0, 0),
                                  (T, 0, 0)])},
        "neck": {"rotate": ro([(0, 0), (0.08, -4), (0.35, 0), (T, 0)])},
        # hands to the cheeks: elbows out, forearms folded up, held while she
        # looks around, then released
        "armL1": {"rotate": ro([(0, 0), (0.12, 46), (0.4, 52), (1.05, 48),
                                (1.3, 10), (T, 0)])},
        "armL2": {"rotate": ro([(0, 0), (0.12, 96), (0.4, 104), (1.05, 98),
                                (1.3, 20), (T, 0)])},
        "armR1": {"rotate": ro([(0, 0), (0.12, -46), (0.4, -52), (1.05, -48),
                                (1.3, -10), (T, 0)])},
        "armR2": {"rotate": ro([(0, 0), (0.12, -96), (0.4, -104), (1.05, -98),
                                (1.3, -20), (T, 0)])},
        "skirt": {"rotate": ro([(0, 0), (0.16, 5), (0.34, -4), (0.52, 2),
                                (0.7, 0), (T, 0)])},
    }
    jump_trail(b, T, amp=1.3)
    anims["hop_alarm"] = b

    # ------------------------------------------------------- hop_memo 2.3 s
    # 备忘: no jump.  She plants a hand on her cheek, tips her head, looks up
    # then down while she remembers, and finishes with one small nod -- the
    # "found it" beat.  Deliberately the quiet one.
    T = 2.3
    b = base_anim(T, eyes=att([(0, "eyes_open"), (0.5, "eyes_up"),
                               (1.2, "eyes_down"), (1.75, "eyes_open")]),
                  mouth=att([(0, "mouth_default"), (1.6, "mouth_smile"),
                             (T, "mouth_smile")]))
    arms_front(b, "r")
    b["bones"] = {
        "root": {"translate": tr([(0, 0, 0), (0.6, 0, -2), (1.5, 0, -2),
                                  (T, 0, 0)])},
        "head": {"rotate": ro([(0, 0), (0.45, 9), (1.5, 8), (1.75, 4),
                               (1.95, 6), (T, 5)]),
                 "translate": tr([(0, 0, 0), (0.45, 5, 0), (1.5, 5, 0),
                                  (1.75, 3, 1), (1.95, 3, -1), (T, 3, 0)])},
        "neck": {"rotate": ro([(0, 0), (0.45, 3), (1.5, 3), (T, 2)])},
        "armR1": {"rotate": ro([(0, 0), (0.4, -40), (1.4, -44), (1.8, -34),
                                (2.05, -6), (T, 0)])},
        "armR2": {"rotate": ro([(0, 0), (0.4, -84), (1.4, -92), (1.8, -70),
                                (2.05, -12), (T, 0)])},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.0, 0.4, 2.5))},
        "hairL3": {"rotate": ro(sine_pairs(T, 1.4, 0.7, 3.0))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.0, 0.5, -2.0))},
        "hairR3": {"rotate": ro(sine_pairs(T, -1.4, 0.8, -2.6))},
        "tail2": {"rotate": ro(sine_pairs(T, 1.6, 0.5))},
        "tailFin": {"rotate": ro(sine_pairs(T, 2.2, 0.8))},
    }
    anims["hop_memo"] = b

    # --------------------------------------------------- drink constants
    # 仰头喝, using the supplied head-up painting rather than tilting the front
    # face.  She turns to the 3/4 body, the head-up face is swapped in, the
    # glass comes up to the lips on the profile and the water drops in three
    # gulps.  Only the head, neck and arms change: the skirt, apron, legs and
    # shoes come from the same 3/4 body the whole way through.
    #
    # Where the sip position comes from: the head-up art is registered 40 px
    # lower than the 3/4 body (tools/side_art.py) so the jaw sits on the collar
    # instead of floating.  The painting has no drawn mouth, only the small red
    # lip mark on the silhouette edge, and that mark sits at (605, 434).
    #
    # The 250 ml bottle is a third of her head tall; at the lips it would lie
    # across her face, so the side chain draws it at 62 % -- the short glass the
    # pose sheet actually shows her drinking from.  Its rim is then 74*0.62 =
    # 45.9 px above the cup bone, and tipped 45 deg the rim lands at
    #   bone + (45.9*sin45, -45.9*cos45)
    # so the bone goes to (605 - 32.5, 434 + 32.5) = (572.5, 466.5), i.e.
    # translate (102.5, -163.5) from its setup (470, 630).  The near hand's grip
    # ends up (607.6, 466.5): 100 px out of a 131 px arm, a natural bent elbow.
    # The far arm cannot join -- 201 px from her lips against 137 px of arm --
    # so it stays at her side.
    SIDE_ROT = 45.0             # glass tipped toward the mouth
    SIDE_POS = (102.5, -163.5)  # cup-bone translate at the sip
    SIDE_SCALE = 0.62
    # where the bottle lives when it is not in her hands: low at the apron
    CUP_LAP_DY = 44.0

    # ------------------------------------------------- water_remind 3.6 s
    # Show the bottle at chest height, then put it away.  Not a drink: the rim
    # stays below the mouth and the water level does not move.  Reach, pull it
    # up in both hands, hold it steady, lower it, set it down -- the whole
    # loop, so the bottle never blinks in or out of existence mid-air.
    T = 3.6
    a = base_anim(T, eyes=att([(0, "eyes_open"), (0.75, "eyes_down"),
                               (2.55, "eyes_open")]),
                  mouth=att([(0, "mouth_default")]))
    a["ik"]["ik_arm_l"] = ikf([(0, 0.0), (0.08, 0.0), (0.34, 1.0),
                               (2.85, 1.0), (3.3, 0.0), (T, 0.0)], True)
    a["ik"]["ik_arm_r"] = ikf([(0, 0.0), (0.08, 0.0), (0.34, 1.0),
                               (2.85, 1.0), (3.3, 0.0), (T, 0.0)], False)
    a["bones"] = {
        "cup": {"translate": tr([(0, 0, CUP_LAP_DY + 4), (0.30, 0, CUP_LAP_DY),
                                 (0.42, 0, CUP_LAP_DY), (0.66, 0, -2),
                                 (0.92, 0, -30), (1.75, 0, -33),
                                 (2.45, 0, -30), (2.66, 0, 6),
                                 (2.86, 0, CUP_LAP_DY), (T, 0, CUP_LAP_DY)]),
                "rotate": ro([(0, 0), (0.92, -5), (2.45, -5), (2.66, 0),
                              (T, 0)])},
        "head": {"rotate": ro([(0, 0), (0.5, 3), (0.92, 5), (1.75, 6),
                               (2.45, 5), (2.86, 1), (3.2, 0), (T, 0)]),
                 "translate": tr([(0, 0, 0), (0.5, 3, 2), (1.75, 4, 3),
                                  (2.45, 3, 2), (2.86, 0, 0), (T, 0, 0)])},
        "neck": {"rotate": ro([(0, 0), (0.92, 2), (2.45, 2), (2.86, 0), (T, 0)])},
        "hairL2": {"rotate": ro(sine_pairs(T, 1.0, 0.8))},
        "hairL3": {"rotate": ro(sine_pairs(T, 1.5, 1.3))},
        "hairR2": {"rotate": ro(sine_pairs(T, -1.0, 0.8))},
        "hairR3": {"rotate": ro(sine_pairs(T, -1.5, 1.3))},
        "tail2": {"rotate": ro(sine_pairs(T, 1.6, 0.6))},
        "tailFin": {"rotate": ro(sine_pairs(T, 2.2, 1.0))},
    }
    a["cup"] = {"attachment": att([(0, "bottle")]),
                "rgba": col([(0, 0.0), (0.30, 0.0), (0.44, 1.0),
                             (2.86, 1.0), (3.00, 0.0)])}
    a["water"] = {"attachment": att([(0, "water")]),
                  "rgba": col([(0, 0.0), (0.30, 0.0), (0.44, 1.0),
                               (2.86, 1.0), (3.00, 0.0)])}
    a["cup_hand_l"] = {"attachment": att([(0, "hand_grip_l")]),
                       "rgba": col([(0, 0.0), (0.30, 0.0), (0.42, 1.0),
                                    (2.66, 1.0), (2.82, 0.0)])}
    a["cup_hand_r"] = {"attachment": att([(0, "hand_grip")]),
                       "rgba": col([(0, 0.0), (0.30, 0.0), (0.42, 1.0),
                                    (2.66, 1.0), (2.82, 0.0)])}
    a["hand_r"] = {"attachment": att([(0, "hand_rest"), (0.40, ""),
                                      (2.84, "hand_rest")]),
                   "rgba": col([(0, 1.0), (0.30, 1.0), (0.40, 0.0),
                                (2.84, 0.0), (3.10, 1.0)])}
    a["hand_l"] = {"attachment": att([(0, "hand_l"), (0.40, ""),
                                      (2.84, "hand_l")]),
                   "rgba": col([(0, 1.0), (0.30, 1.0), (0.40, 0.0),
                                (2.84, 0.0), (3.10, 1.0)])}
    anims["water_remind"] = a

    # drink_in 1.2 s -- turn to the side, the glass is already waiting at her
    # waist, both hands take it and lift it to the lips.  The front set is
    # faded out rather than popped: the two paintings share a canvas and a
    # figure height, so a fast cross-fade reads as a turn, not a costume change.
    T = 1.2
    a = base_anim(T, eyes=att([(0, "eyes_open")]),
                  mouth=att([(0, "mouth_default")]))
    # a short cross-fade: the faces of the two paintings do not sit on the same
    # pixels, so a long blend shows both pairs of eyes at once.  0.10 s is two
    # frames at 24 fps -- long enough to read as motion, short enough that no
    # frame is a double exposure.
    fade_out(a, FRONT_SLOTS, 0.02, 0.09)
    fade_in(a, SIDE_SLOTS, 0.02, 0.09)
    a["bones"] = {
            "cup": {"translate": tr([(0, 0, CUP_LAP_DY), (0.46, 0, CUP_LAP_DY),
                                     (0.96, SIDE_POS[0], SIDE_POS[1]),
                                     (T, SIDE_POS[0], SIDE_POS[1])]),
                    "rotate": ro([(0, 0), (0.46, 0), (0.98, SIDE_ROT),
                                  (T, SIDE_ROT)]),
                    "scale": sc([(0, SIDE_SCALE, SIDE_SCALE),
                                 (T, SIDE_SCALE, SIDE_SCALE)])},
            "root": {"translate": tr([(0, 0, 0), (0.52, 0, 1.5), (0.80, 0, -1.0),
                                      (T, 0, 0)])},
            "neck": {"rotate": ro([(0, 0), (0.52, 1.2), (T, 0)])},
    }
    a["cup_hand_l"] = {"attachment": att([(0, "")]), "rgba": col([(0, 0.0)])}
    a["cup_hand_r"] = {"attachment": att([(0, "")]), "rgba": col([(0, 0.0)])}
    # the glass only shows once the near hand is on it.  At 0.20 it appeared on
    # the apron 0.26 s before the arm arrived, so she turned past a bottle
    # floating unsupported in front of her skirt.
    a["cup"] = {"attachment": att([(0, "bottle")]),
                "rgba": col([(0, 0.0), (0.34, 0.0), (0.46, 1.0)])}
    a["water"] = {"attachment": att([(0, "water")]),
                  "rgba": col([(0, 0.0), (0.34, 0.0), (0.46, 1.0)])}
    a["ik"]["s_ik_arm_r"] = ikf([(0, 0.0), (0.16, 0.0), (0.46, 1.0), (T, 1.0)], False)
    anims["drink_in"] = a

    def sip_clip(start_lvl, end_lvl):
        T = 1.0
        step = (start_lvl - end_lvl) / 3.0
        lv = []
        for t, i in ((0, 0), (0.16, 0), (0.22, 1), (0.40, 1),
                     (0.46, 2), (0.60, 2), (0.68, 3), (0.82, 3), (T, 3)):
            lv.append((t, 1.0, start_lvl - step * i))
        b = base_anim(T, eyes=att([(0, "eyes_open")]),
                      mouth=att([(0, "mouth_default")]))
        fade_out(b, FRONT_SLOTS)
        fade_in(b, SIDE_SLOTS)
        # the gulps show in the water level, not in the head: three bobs a
        # second read as a twitch.  The glass holds its tilt and the throat
        # does the work, one small swallow of the neck per gulp.
        b["bones"] = {
                "cup": {"translate": tr([(0, SIDE_POS[0], SIDE_POS[1]),
                                         (T, SIDE_POS[0], SIDE_POS[1])]),
                        "rotate": ro([(0, SIDE_ROT), (T, SIDE_ROT)]),
                        "scale": sc([(0, SIDE_SCALE, SIDE_SCALE),
                                     (T, SIDE_SCALE, SIDE_SCALE)])},
                "neck": {"rotate": ro([(0, 0), (0.20, -1.4), (0.34, 0),
                                       (0.44, -1.4), (0.58, 0), (0.66, -1.4),
                                       (0.80, 0), (T, 0)])},
                "water": {"scale": sc(lv)},
        }
        b["cup"] = {"attachment": att([(0, "bottle")]), "rgba": col([(0, 1.0)])}
        b["water"] = {"attachment": att([(0, "water")]), "rgba": col([(0, 1.0)])}
        b["ik"]["s_ik_arm_r"] = ikf([(0, 1.0), (T, 1.0)], False)
        return b

    # three sips drain the 250 ml bottle: 1.00 -> 0.70 -> 0.40 -> 0.12
    anims["drink_sip"] = sip_clip(1.00, 0.70)
    anims["drink_sip2"] = sip_clip(0.70, 0.40)
    anims["drink_sip3"] = sip_clip(0.40, 0.12)

    # drink_out 1.2 s -- set the glass down at her waist, let go, turn back to
    # the front set.  The front slots are faded back in at the very end and the
    # side set left at zero, so whatever clip runs next starts from the front
    # body no matter which one it is.
    T = 1.2
    a = base_anim(T, eyes=att([(0, "eyes_open")]),
                  mouth=att([(0, "mouth_default")]))
    # attach the side set even though the chain normally arrives here with it
    # already in place: a clip that only faded it out would show the glass
    # lowering on its own if it were ever entered from a reset skeleton
    fade_in(a, SIDE_SLOTS)
    # same 0.10 s cross-fade as drink_in, for the same reason: a longer one
    # double-exposes the 3/4 face over the front face
    fade_out(a, SIDE_SLOTS, 0.87, 0.94)
    fade_in(a, FRONT_SLOTS, 0.87, 0.94, attach=False)
    a["bones"] = {
            "cup": {"translate": tr([(0, SIDE_POS[0], SIDE_POS[1]),
                                     (0.62, 0, CUP_LAP_DY),
                                     (T, 0, CUP_LAP_DY)]),
                    "rotate": ro([(0, SIDE_ROT), (0.62, 0), (T, 0)]),
                    # back to full size only once the glass is invisible, so a
                    # later water_remind gets the 250 ml bottle it expects
                    "scale": sc([(0, SIDE_SCALE, SIDE_SCALE),
                                 (0.85, SIDE_SCALE, SIDE_SCALE),
                                 (0.87, 1.0, 1.0), (T, 1.0, 1.0)])},
            "root": {"translate": tr([(0, 0, 0), (0.30, 0, -1.0),
                                      (0.66, 0, 1.5), (0.90, 0, 0), (T, 0, 0)])},
    }
    a["cup"] = {"attachment": att([(0, "bottle")]),
                "rgba": col([(0, 1.0), (0.68, 1.0), (0.86, 0.0)])}
    a["water"] = {"attachment": att([(0, "water")]),
                  "rgba": col([(0, 1.0), (0.68, 1.0), (0.86, 0.0)])}
    a["ik"]["s_ik_arm_r"] = ikf([(0, 1.0), (0.60, 1.0), (0.88, 0.0), (T, 0.0)], False)
    anims["drink_out"] = a

    # slot channels live under "slots"; the clips above keep them at the top
    # level for readability.
    slot_names = {name for name, _bone, _att in SLOTS}
    for a in anims.values():
        ch = a.setdefault("slots", {})
        for name in list(a):
            if name in slot_names:
                ch[name] = a.pop(name)
    return anims




# ------------------------------------------------------------ skeleton

def mirror_animations(skel):
    """Bones and meshes are authored straight in skeleton space (y-up, the
    top of the character at y = 0, so the runtime's y flip lands them at
    source y - SRC_TOP on screen).  Animation channels are authored in screen
    space (+y down, clockwise rotations) because those are the values the
    player sees; the runtime flip cancels the negations below."""
    for timeline in skel["animations"].values():
        for channels in timeline.get("bones", {}).values():
            for key in channels.get("translate", []):
                key["y"] = -key["y"]
            for key in channels.get("rotate", []):
                key["value"] = -key["value"]
    for bone in skel["bones"]:
        if "rotation" in bone:
            bone["rotation"] = -bone["rotation"]


def write_atlas(path, page_name, page_size, regions):
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


def pack(regions, width=2048):
    """Shelf pack.  regions: [(name, image, rect)] -> placements + page size."""
    items = sorted(regions, key=lambda r: (-(r[2][3] - r[2][1]), -(r[2][2] - r[2][0])))
    placements = []
    x = 0
    y = 0
    shelf_h = 0
    for name, img, rect in items:
        w = rect[2] - rect[0]
        h = rect[3] - rect[1]
        if x + w + GUTTER > width:
            x = 0
            y += shelf_h + GUTTER
            shelf_h = 0
        placements.append((name, (x, y), (w, h)))
        x += w + GUTTER
        shelf_h = max(shelf_h, h)
    return placements, (width, y + shelf_h + GUTTER)


def debug_composite(layers, out_dir):
    W = H = 1024
    comp = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    for _slot, _bone, region in SLOTS:
        if not region:
            continue  # hidden at setup (the cup)
        comp.alpha_composite(layers[region][0], layers[region][1][:2])
    comp.save(os.path.join(out_dir, "rest_composite.png"))
    return comp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="assets/art/pet_portrait.png")
    ap.add_argument("--out", default="game/assets/pet_spine")
    ap.add_argument("--debug", default="tools/_debug/layers")
    args = ap.parse_args()

    src = Image.open(args.src).convert("RGBA")
    W, H = src.size
    layers, mk, hair_masks = build_layers(src)
    # the side view comes from the two supplied angle paintings (tools/
    # side_art.py); they share the front canvas so their meshes need no
    # registration of their own
    import side_art
    layers.update(side_art.rig_layers())
    from rig_repair import repair_layers
    repair_layers(layers)
    print("layers:", ", ".join("%s %dx%d" % (n, layers[n][1][2] - layers[n][1][0],
                                             layers[n][1][3] - layers[n][1][1])
                               for n in sorted(layers)))
    if os.environ.get("FISHPET_RECTS"):
        for n in sorted(layers):
            print("  rect", n, layers[n][1])

    # ---- build meshes
    meshes = {}
    for name, (img, rect) in layers.items():
        if name in GRIDS:
            fn = {"body": w_body, "tail": w_tail, "skirt": w_skirt,
                  "hair_l": w_hair("L"), "hair_r": w_hair("R"),
                  "arm_up_l": w_arm_up("L"), "arm_up_r": w_arm_up("R"),
                  "arm_fore_l": w_arm_fore("L"), "arm_fore_r": w_arm_fore("R")}[name]
            meshes[name] = make_grid(rect, GRIDS[name], fn)
        else:
            bone = {"head": "head", "hand_l": "handL", "hand_rest": "handR",
                    "hand_open": "handR",
                    # the grip hands ride on the bottle's grip bones
                    "hand_grip": "gripR", "hand_grip_l": "gripL",
                    "bottle": "cup", "water": "water",
                    "book": "book", "pen": "pen", "book_hand": "workL",
                    "hair_back": "root",
                    "fish": "fish",
                    "fish_hand_l": "slackL", "fish_hand_r": "slackR",
                    # side set: rigid quads on their own bones
                    "s_hair_back": "root", "s_body": "root", "s_head": "head",
                    "s_head_rest": "head",
                    "s_body_up": "root",
                    "s_arm_up_l": "s_armL1", "s_arm_up_r": "s_armR1",
                    "s_arm_fore_l": "s_armL2", "s_arm_fore_r": "s_armR2",
                    "s_arm_fore_l_open": "s_armL2", "s_arm_fore_r_open": "s_armR2",
                    "hand_open_l": "handL"}.get(name, "head")
            meshes[name] = make_quad(rect, bone)
        if name == "drink_arms":
            meshes[name] = make_quad(rect, "drink_prop")
        if name in ("d_upper_l", "d_upper_r", "d_fore_l", "d_fore_r"):
            bone = {"d_upper_l": "d_armL1", "d_upper_r": "d_armR1",
                    "d_fore_l": "d_armL2", "d_fore_r": "d_armR2"}[name]
            meshes[name] = make_quad(rect, bone)
        if name in ("d_fore_l", "d_fore_r"):
            from rig_repair import drink_sleeve_weights
            meshes[name] = make_grid(rect, 3.0, drink_sleeve_weights(name[-1]))
        if name == "slack_sleeve_r":
            from rig_repair import slack_sleeve_weights
            meshes[name] = make_grid(rect, 3.0, slack_sleeve_weights)
        if name in ("s_arm_up_l", "s_arm_up_r"):
            from rig_repair import side_shoulder_weights
            meshes[name] = make_grid(rect, 5.0, side_shoulder_weights(name[-1]))
        if name == "work_arms":
            from rig_repair import work_weights
            meshes[name] = make_grid(rect, 4.0, work_weights)

    # ---- atlas
    regions = [(name, layers[name][0], layers[name][1]) for name in layers]
    placements, page_size = pack(regions)
    os.makedirs(args.out, exist_ok=True)
    page = Image.new("RGBA", page_size, (0, 0, 0, 0))
    for name, pos, _size in placements:
        page.alpha_composite(layers[name][0], pos)
    page.save(os.path.join(args.out, "pet.png"))
    write_atlas(os.path.join(args.out, "pet.atlas"), "pet.png", page_size,
                [(n, pos, (layers[n][1][2] - layers[n][1][0],
                           layers[n][1][3] - layers[n][1][1]))
                 for n, pos, _s in placements])

    # ---- silhouette for hit testing
    bb = src.getchannel("A").getbbox()
    # Safe canvas-aligned fallback until preview_pose.py --all --silhouette
    # replaces it with the sampled animation union. Never stretch an idle crop.
    silhouette = Image.new("RGBA", src.size, "white")
    silhouette.putalpha(src.getchannel("A").filter(ImageFilter.MaxFilter(151)))
    silhouette.save(os.path.join(args.out, "pet_silhouette.png"))
    print("silhouette canvas", src.size, "(run preview_pose.py --all --silhouette)")

    # ---- skeleton
    bone_json = []
    for name, parent, x, y in BONES:
        wx, wy = img_to_world(x, y)
        if parent is None:
            lx, ly = wx, wy
        else:
            px, py = BONE_WORLD[parent]
            dx, dy = wx - px, wy - py
            pr = ARM_AIM.get(parent)
            if pr:
                # the parent's local frame is turned; express the child offset in it
                c, s = math.cos(math.radians(pr)), math.sin(math.radians(pr))
                lx, ly = c * dx + s * dy, -s * dx + c * dy
            else:
                lx, ly = dx, dy
        bone = {"name": name, "x": round(lx, 3), "y": round(ly, 3)}
        if name in ARM_AIM:
            # authored in screen convention; mirror_animations negates it
            bone["rotation"] = round(-ARM_AIM[name], 3)
        if parent:
            bone["parent"] = parent
        bone_json.append(bone)

    # The two-bone IK solver reads the CHILD bone's length (BoneData.length) as
    # the forearm length it needs to solve the elbow triangle.  A bone with no
    # length makes that length 0 and the solver degenerates, so set a length for
    # each arm-chain bone from the distance to its child.
    _children = {}
    for name, parent, _x, _y in BONES:
        _children.setdefault(parent, []).append(name)
    for bone in bone_json:
        if bone["name"] in ("armL1", "armL2", "armR1", "armR2",
                            "d_armL1", "d_armL2", "d_armR1", "d_armR2",
                            "s_armL1", "s_armL2", "s_armR1", "s_armR2"):
            kids = _children.get(bone["name"])
            if kids:
                wx, wy = BONE_WORLD[bone["name"]]
                cx, cy = BONE_WORLD[kids[0]]
                bone["length"] = round(math.hypot(cx - wx, cy - wy), 3)

    slot_json = []
    for s, b, a in SLOTS:
        slot = {"name": s, "bone": b}
        if a:
            slot["attachment"] = a
        slot_json.append(slot)
    skins = {"name": "default", "attachments": {}}
    for s, b, a in SLOTS:
        if s == "hand_r":
            skins["attachments"][s] = {"hand_rest": meshes["hand_rest"],
                                       "hand_open": meshes["hand_open"]}
        elif s == "hand_l":
            skins["attachments"][s] = {"hand_l": meshes["hand_l"]}
        elif s == "eyes":
            skins["attachments"][s] = {m: meshes[m] for m in
                                       ("eyes_open", "eyes_half", "eyes_closed", "eyes_happy",
                                        "eyes_left", "eyes_right", "eyes_up", "eyes_down")}
        elif s == "mouth":
            skins["attachments"][s] = {m: meshes[m] for m in
                                       ("mouth_default", "mouth_sip", "mouth_smile")}
        elif s == "cup":
            # hidden at setup; the drink clips attach it by name
            skins["attachments"][s] = {"bottle": meshes["bottle"]}
        elif s == "water":
            skins["attachments"][s] = {"water": meshes["water"]}
        elif s == "cup_hand_l":
            skins["attachments"][s] = {"hand_grip_l": meshes["hand_grip_l"]}
        elif s == "cup_hand_r":
            skins["attachments"][s] = {"hand_grip": meshes["hand_grip"]}
        elif s == "arm_fore_l_front":
            skins["attachments"][s] = {"arm_fore_l": meshes["arm_fore_l"]}
        elif s == "arm_fore_r_front":
            skins["attachments"][s] = {"arm_fore_r": meshes["arm_fore_r"]}
        elif s == "hand_l_front":
            skins["attachments"][s] = {"hand_l": meshes["hand_l"],
                                       "hand_open_l": meshes["hand_open_l"]}
        elif s == "hand_r_front":
            skins["attachments"][s] = {"hand_rest": meshes["hand_rest"],
                                       "hand_open": meshes["hand_open"]}
        elif s == "pen_hand":
            skins["attachments"][s] = {"hand_pen": meshes["hand_pen"]}
        elif s == "s_head":
            skins["attachments"][s] = {n: meshes[n] for n in ("s_head", "s_head_rest")}
        elif s == "s_body":
            skins["attachments"][s] = {n: meshes[n] for n in ("s_body", "s_body_up")}
        elif s in ("s_arm_fore_l", "s_arm_fore_r"):
            skins["attachments"][s] = {n: meshes[n] for n in (s, s + "_open")}
        elif s.startswith("s_"):
            # hidden at setup; the drink clips attach the side set by name
            skins["attachments"][s] = {s: meshes[s]}
        elif s in ("arm_up_l_front", "arm_up_r_front"):
            source = s.removesuffix("_front")
            skins["attachments"][s] = {source: meshes[source]}
            if s == "arm_up_r_front":
                skins["attachments"][s]["slack_sleeve_r"] = meshes["slack_sleeve_r"]
        elif s in ("book", "pen", "fish", "drink_arms", "work_arms", "book_hand",
                   "d_upper_l", "d_upper_r", "d_fore_l", "d_fore_r",
                   "fish_hand_l", "fish_hand_r"):
            # hidden at setup; the state clips attach them by their slot name
            skins["attachments"][s] = {s: meshes[s]}
        elif s in ("fish_hand_l_front", "fish_hand_r_front"):
            # front duplicates of the hugging palms: same art, later in the
            # draw order, so they sit over the sleeves that wrap the plush
            skins["attachments"][s] = {"fish_hand_" + s[10]: meshes["fish_hand_" + s[10]]}
        else:
            skins["attachments"][s] = {a: meshes[a]}

    skel = {
        "skeleton": {
            "spine": "4.2.43",
            "x": 0.0, "y": 0.0,
            "width": 599, "height": 820,
            "images": "./",
            "audio": "",
        },
        "bones": bone_json,
        "slots": slot_json,
        "ik": IK,
        "skins": [skins],
        "animations": build_animations(),
    }
    from pose_refinement import refine
    refine(skel)
    mirror_animations(skel)
    with open(os.path.join(args.out, "pet.spine-json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(skel, fh, ensure_ascii=False, separators=(",", ":"))

    # ---- debug
    if args.debug:
        os.makedirs(args.debug, exist_ok=True)
        # the side set is hidden at setup; drawing it into the rest composite
        # would lay a second character over the first and redden the whole diff
        comp = debug_composite({k: v for k, v in layers.items()
                                if not k.startswith("s_")}, args.debug)
        diff = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        dp = diff.load()
        op = src.load()
        cp = comp.load()
        n = 0
        for y in range(H):
            for x in range(W):
                a = op[x, y]
                b = cp[x, y]
                if max(abs(a[i] - b[i]) for i in range(4)) > 14:
                    dp[x, y] = (255, 0, 0, 255)
                    n += 1
        diff.save(os.path.join(args.debug, "diff.png"))
        for name in layers:
            img, rect = layers[name]
            bg = Image.new("RGBA", img.size, (255, 0, 255, 255))
            bg.alpha_composite(img)
            bg.convert("RGB").save(os.path.join(args.debug, "view_%s.png" % name))
        print("rest diff pixels:", n)

    print("page", page_size, "regions", len(placements))
    print("json bytes", os.path.getsize(os.path.join(args.out, "pet.spine-json")))


if __name__ == "__main__":
    main()
