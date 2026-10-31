"""Cut the painted hands out of the pose reference sheet.

The rig's hands used to be drawn with PIL primitives.  Next to a painted
portrait a shape built from ellipses reads as a sticker, and at the 0.41x
display size the four fingers merge into a mitten with a claw.  The artist's
five-pose sheet has the same character's hands painted in exactly the poses
the rig needs, so the hands are lifted from it instead of redrawn.

The matte is a flood from a seed point through "walkable" pixels, where the
barriers are the three things that surround a hand in these panels: the dark
line art, the flat light-blue panel background, and the whale's blue.  Skin,
including its white specular highlights, is the only thing left to walk on, so
the flood fills the hand and stops at its own contour.  Because the flood
stops at the line art, the dark outline is added back as a 3 px ring -- that
outline is what gives the hand its weight against the navy sleeve.

Each hand is returned as an RGBA sprite trimmed to its own bounding box,
together with the wrist point in sprite coordinates -- the point that has to
land on the rig's hand bone -- and the direction from wrist to fingertips.

Run `python tools/hand_cut.py` for a contact sheet of every cut hand.
"""
import os
from collections import deque

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
SHEET = os.path.join(ROOT, "assets", "art", "pose_references",
                     "fishpet-five-poses-20261024-v1.png")
BG = (233, 238, 246)            # the sheet's flat panel background

# name -> where the hand is and which way it points, all in sheet pixels
#   box       : window around the hand; the seed decides which region is the hand
#   seed      : a point well inside the hand.  Panel 1's hands sit right under
#               the chin, whose skin is the same colour, so "largest blob"
#               grabbed the face there.
#   wrist     : where the cuff ends and the skin begins; this lands on the bone
#   direction : wrist -> fingertips.  The sprite is rotated at paste time to
#               line this up with the angle the pose wants.
CUTS = {
    "cradle_l": dict(box=(82, 356, 152, 412), seed=(116, 389),
                     wrist=(94, 392), direction=(1.0, -0.15)),
    # panel 2, the presented palm: fingers right, thumb up, wrist at lower left
    # the wrist sits a little way back inside the cuff: the rig's forearm art
    # stops at the white frill, and anchoring on the first bare pixel of skin
    # left a gap of bare hair between the sleeve and the palm
    "open_r": dict(box=(752, 258, 872, 352), seed=(805, 315),
                   wrist=(777, 316), direction=(1.0, -0.05)),
    # panel 1, the hand stroking the whale's back: fingers up-left, cuff at
    # lower right
    "stroke_r": dict(box=(190, 282, 286, 348), seed=(216, 302),
                     wrist=(250, 320), direction=(-0.87, -0.50)),
}


def _barrier(px):
    r, g, b = px
    if 0.299 * r + 0.587 * g + 0.114 * b < 150:      # line art, navy sleeve
        return True
    # the panel background is light blue-grey: bluer than red and bright.  The
    # whites inside the hand (specular highlights) are neutral, so they stay
    # walkable -- a distance-to-BG test alone swallows them and punches holes
    # straight through the palm.
    if b - r >= 8 and b >= 238:
        return True
    return b - r > 25                                 # whale, hair


def hand_alpha(img, seed, wrist, direction, warm_only=False):
    """Alpha for one hand crop, cut square across the wrist."""
    px = img.load()
    w, h = img.size

    walk = Image.new("L", (w, h), 0)
    wp = walk.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if not _barrier(px[x, y]) and (not warm_only or (r - g > 4 and r - b > 6)):
                wp[x, y] = 255
    # one pixel of erosion seals pinholes in the contour, which would otherwise
    # let the flood escape into the background through an anti-aliased gap
    walk = walk.filter(ImageFilter.MinFilter(3))
    wp = walk.load()

    if not wp[seed]:
        raise ValueError("seed %r landed on a barrier" % (seed,))
    region = Image.new("L", (w, h), 0)
    rp = region.load()
    q = deque([seed])
    seen = {seed}
    while q:
        x, y = q.popleft()
        rp[x, y] = 255
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in seen \
                    and wp[nx, ny]:
                seen.add((nx, ny))
                q.append((nx, ny))
    region = region.filter(ImageFilter.MaxFilter(3))

    # the specular highlights inside the hand are neutral, so the warmth test
    # stops the flood on them: fill whatever the flood could not reach, i.e.
    # the regions enclosed by the hand rather than open to the crop edge
    inv = Image.eval(region, lambda v: 255 - v)
    ip = inv.load()
    outside = Image.new("L", (w, h), 0)
    op_ = outside.load()
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if ip[x, y] and not op_[x, y]:
                op_[x, y] = 255
                q.append((x, y))
    for y in range(h):
        for x in (0, w - 1):
            if ip[x, y] and not op_[x, y]:
                op_[x, y] = 255
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < w and 0 <= ny < h and ip[nx, ny] and not op_[nx, ny]:
                op_[nx, ny] = 255
                q.append((nx, ny))
    region = ImageChops.lighter(region, Image.eval(outside, lambda v: 255 - v))

    # the line art the flood stopped at, and only that: a few pixels out from
    # the region, not everything dark in the crop, and not the whale's blue --
    # the whale is dark enough to look like line art and would come along as a
    # blue halo around every finger
    dark = Image.new("L", (w, h), 0)
    dp = dark.load()
    for y in range(h):
        for x in range(w):
            r, g, b = px[x, y]
            if 0.299 * r + 0.587 * g + 0.114 * b < 150 and b - r < 30:
                dp[x, y] = 255
    ring = ImageChops.subtract(region.filter(ImageFilter.MaxFilter(7)), region)
    alpha = ImageChops.lighter(region, ImageChops.multiply(ring, dark))

    # cut the forearm off square at the wrist; the straight edge that leaves
    # sits under the sleeve's cuff, which is where the rig's wrist is
    dl = (direction[0] ** 2 + direction[1] ** 2) ** 0.5
    dx, dy = direction[0] / dl, direction[1] / dl
    ap = alpha.load()
    for y in range(h):
        for x in range(w):
            if (x - wrist[0]) * dx + (y - wrist[1]) * dy < -1.0:
                ap[x, y] = 0

    return alpha.filter(ImageFilter.GaussianBlur(0.6)) \
        .point(lambda v: min(255, int(v * 1.4)))


def cut(name, box, seed, wrist, direction, mirror=False):
    """Return (sprite, wrist point in sprite pixels, direction)."""
    sheet = Image.open(SHEET).convert("RGB")
    chip = sheet.crop(box)
    local_w = (wrist[0] - box[0], wrist[1] - box[1])
    local_s = (seed[0] - box[0], seed[1] - box[1])
    if name == "cradle_l":
        # The white whale belly touches the fingers: a colour flood either
        # leaks into it or erodes the pale fingertips. Trace this painted
        # contour explicitly while retaining the original colours/highlights.
        points = [(94, 391), (95, 382), (104, 374), (116, 365),
                  (119, 365), (120, 367), (118, 371), (114, 374),
                  (132, 374), (141, 378), (142, 381), (132, 382),
                  (143, 382), (144, 385), (139, 390), (132, 395),
                  (137, 395), (138, 398), (133, 401), (110, 406),
                  (101, 405), (96, 401)]
        alpha = Image.new("L", (chip.width * 4, chip.height * 4))
        ImageDraw.Draw(alpha).polygon([((x - box[0]) * 4, (y - box[1]) * 4)
                                       for x, y in points], fill=255)
        alpha = alpha.resize(chip.size, Image.Resampling.LANCZOS)
    else:
        alpha = hand_alpha(chip, local_s, local_w, direction)
    out = chip.convert("RGBA")
    out.putalpha(alpha)
    bb = alpha.getbbox()
    out = out.crop(bb)
    wx, wy = local_w[0] - bb[0], local_w[1] - bb[1]
    d = direction
    if mirror:
        out = out.transpose(Image.FLIP_LEFT_RIGHT)
        wx = out.width - wx
        d = (-d[0], d[1])
    return out, (wx, wy), d


def cut_all():
    return {name: cut(name, **kw) for name, kw in CUTS.items()}


# rig attachment name -> (which cut, where its wrist goes on the 1024 canvas)
#   wx, wy : the rig's wrist anchor, i.e. the hand bone's setup position
#   ang    : the rest direction of that forearm, so the hand hangs off the
#            bone with no wrist rotation at rest.  Everything else -- the
#            raised presentations, the hugging hands -- comes from the bones.
#   mirror : the left hand is the right hand's painted counterpart
HANDS = {
    "hand_open":   ("open_r",   dict(wx=607, wy=676, ang=59.5)),
    # the left forearm runs down-LEFT from the elbow, i.e. +123.3 deg in this
    # y-down convention, so the resting palm must point that way too
    "hand_open_l": ("open_r",   dict(wx=338, wy=663, ang=123.3, mirror=True)),
    # cradling: the palm comes up from below and its fingers point up-right
    # along the whale's belly, exactly as the artist painted it in the hug
    "fish_hand_l": ("cradle_l", dict(wx=375, wy=706, ang=20.0)),
    # the stroking hand lies along the whale's back with the fingers pointing
    # up-left at the head, which is how the artist painted it
    "fish_hand_r": ("stroke_r", dict(wx=470, wy=607, ang=-165.0)),
}


def place_hand(sprite, wrist, direction, wx, wy, ang=0.0, scale=1.0,
               mirror=False, size=1024):
    """Paste a cut hand onto the rig canvas with its wrist at (wx, wy).

    `ang` is the on-canvas angle, in degrees clockwise from +x, that the
    fingers should point along -- for a bone-carried attachment that is the
    rest direction of its forearm.  The sprite is rotated about its own wrist
    so the wrist stays exactly on the bone.
    """
    import math

    img = sprite
    wx_, wy_ = wrist
    if mirror:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        wx_ = img.width - wx_
        direction = (-direction[0], direction[1])
    if scale != 1.0:
        img = img.resize((max(1, round(img.width * scale)),
                          max(1, round(img.height * scale))), Image.LANCZOS)
        wx_, wy_ = wx_ * scale, wy_ * scale

    pad = max(img.size)
    stage = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad),
                      (0, 0, 0, 0))
    stage.paste(img, (pad, pad))
    px, py = wx_ + pad, wy_ + pad
    turn = math.degrees(math.atan2(direction[1], direction[0])) - ang
    src = stage.rotate(turn, center=(px, py), resample=Image.BICUBIC)

    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(src, (int(round(wx - px)), int(round(wy - py))), src)
    return out


if __name__ == "__main__":
    tiles = []
    for name, kw in CUTS.items():
        img, w, d = cut(name, **kw)
        tiles.append((name, img, w, d))
        print(name, img.size, "wrist", w, "dir", d)
    scale = 6
    pad = 16
    W = sum(t[1].width * scale for t in tiles) + pad * (len(tiles) + 1)
    H = max(t[1].height for t in tiles) * scale + 52
    sheet = Image.new("RGBA", (W, H), (108, 113, 132, 255))
    x = pad
    d = ImageDraw.Draw(sheet)
    for name, img, w, dirn in tiles:
        big = img.resize((img.width * scale, img.height * scale), Image.LANCZOS)
        y = 8
        sheet.alpha_composite(big, (x, y))
        cx, cy = x + w[0] * scale, y + w[1] * scale
        d.line([(cx - 9, cy), (cx + 9, cy)], fill=(255, 70, 70), width=2)
        d.line([(cx, cy - 9), (cx, cy + 9)], fill=(255, 70, 70), width=2)
        d.line([(cx, cy), (cx + dirn[0] * 70, cy + dirn[1] * 70)], fill=(255, 70, 70))
        d.text((x, H - 18), name, fill=(240, 240, 250))
        x += big.width + pad
    sheet.convert("RGB").save(os.path.join(ROOT, "tools", "_debug", "hands_cut.png"))
    print("wrote tools/_debug/hands_cut.png")
