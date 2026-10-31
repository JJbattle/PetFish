"""Split the supplied 3/4 and head-up paintings into rig layers.

`assets/art/angle_references/20261024-v1/` holds three 1254 px paintings that
were generated against the front portrait.  They are flat composites: one
character per angle, arms hanging, no separated parts.  This module registers
them onto the 1024 px rig canvas and cuts the pieces the drink chain needs.

Layer set (mirrors the front rig, so the same slot/weight code applies):

    hair_back   the whole painting behind everything, arms patched out, and the
                painted face (skin, eyes, lashes, blush) dropped so a tilted
                head cannot reveal the face the body was drawn with
    body        rows below the collar line, arms patched out
    arm_up_*    sleeve above the elbow
    arm_fore_*  sleeve below the elbow with the white cuff, gold trim and the
                painted fist baked in -- the fist IS the hand, so the drink has
                exactly two hands and no second pair of grip sprites
    head        the 3/4 head + neck, cut at the collar line
    head_up     the same cut from the head-up painting; the drink swaps only
                this in, so the skirt, apron, legs and shoes never change

Registration: the 1254 px sheets are drawn at a larger scale than the front
portrait (1146 px tall against 816).  Height-fit -- not bbox-centre -- puts the
eyes and the brooch on top of the front's within a couple of pixels, so `S` is
the figure-height ratio and the translation puts the feet on y = 950 and the
body axis on x = 470.

Run `python tools/side_art.py` to write `tools/_debug/side_layers.png`.
"""
import os
import sys
from collections import deque

from PIL import Image, ImageChops, ImageDraw, ImageFilter

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REF = os.path.join(ROOT, "assets", "art", "angle_references", "20261024-v1")
DEBUG = os.path.join(ROOT, "tools", "_debug")

sys.path.insert(0, os.path.join(ROOT, "tools"))
from build_spine import cut, flood_mask, is_skin, union      # noqa: E402

# figure height 1146/1149 px -> 816 px, the front portrait's height
S = 816.0 / 1146.0
# x / y translation after scaling: feet bottom -> y 950, body axis -> x 470.
# The repaired raised-head pose uses its matching armless body (rig_repair),
# so it no longer needs to be sunk onto the unrelated three-quarter collar.
REG = {
    "r34": (1.1, 90.6),
    "up": (-3.8, 100.0),
}
# rows <= this belong to the head layer.  Both cuts land on the white collar
# frill, which is the one place the two paintings agree.  The head-up cut is
# deeper than its collar (its neck runs to row 495 because the head is tipped
# back): cutting at 490 instead leaves the up chin sliced off flat, and the
# 3/4 painting's own chin shows underneath as a second jaw.
NECK = {"r34": 500, "up": 515}

# elbow split: the sleeve is cut just above the joint and the forearm keeps a
# few rows of overlap so the two halves cannot open a gap when it bends
ELBOW_Y = {"l": 612, "r": 610}
SLEEVE_SEED = {"l": (400, 620), "r": (578, 600)}
# the cuff + fist live here.  The left box stops at x = 412: past that is the
# apron's white frill, which the pale test would otherwise drag onto the arm.
CUFF_BOX = {"l": (316, 612, 412, 708), "r": (572, 626, 640, 704)}
FIST_SEED = {"l": (368, 682), "r": (610, 676)}


def register(key):
    im = Image.open(os.path.join(REF, "pet_%s_reference.png" % key)).convert("RGBA")
    n = im.resize((round(im.width * S), round(im.height * S)), Image.LANCZOS)
    out = Image.new("RGBA", (1024, 1024), (0, 0, 0, 0))
    dx, dy = REG[key]
    out.alpha_composite(n, (round(dx), round(dy)))
    return out


def navy(r, g, b, a):
    return (a > 120 and max(r, g, b) >= 70 and b >= max(r, g, b)
            and max(r, g, b) < 175 and b > 70)


def gold(r, g, b, a):
    return a > 120 and r > 170 and 110 < g < 205 and b < 130 and r - b > 70


def pale(r, g, b, a):
    return (a > 100 and min(r, g, b) > 150 and b >= g - 3
            and max(r, g, b) - min(r, g, b) <= 34)


def dark(r, g, b, a):
    return a > 100 and (r + g + b) < 300


def box_mask(size, box, pred, im):
    m = Image.new("L", size, 0)
    mp = m.load()
    p = im.load()
    for y in range(box[1], box[3]):
        for x in range(box[0], box[2]):
            if pred(*p[x, y]):
                mp[x, y] = 255
    return m


def flood_in_box(im, box, seed, pred, barrier=None, grow=3):
    """Region-grow from `seed` across `pred` pixels, never leaving `box`."""
    W, H = im.size
    p = im.load()
    m = Image.new("L", (W, H), 0)
    mp = m.load()
    q = deque([seed])
    mp[seed] = 255
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (box[0] <= nx < box[2] and box[1] <= ny < box[3]) or mp[nx, ny]:
                continue
            px = p[nx, ny]
            if barrier and barrier(*px):
                continue
            if pred(*px):
                mp[nx, ny] = 255
                q.append((nx, ny))
    return m.filter(ImageFilter.MaxFilter(grow * 2 + 1))


def arm_masks(im):
    """Sleeve / cuff+trim+fist masks per side."""
    out = {}
    for side in ("l", "r"):
        sleeve = flood_mask(im, SLEEVE_SEED[side], navy)
        box = CUFF_BOX[side]
        cuff = ImageChops.lighter(box_mask(im.size, box, pale, im),
                                  box_mask(im.size, box, gold, im))
        fist = flood_in_box(im, box, FIST_SEED[side],
                            lambda r, g, b, a: is_skin(r, g, b, a) or pale(r, g, b, a),
                            barrier=dark, grow=2)
        # the pale test also matches the apron, which hangs a hand's width from
        # the fist inside the same box.  Taken whole, the box turns the hole in
        # the body into a flat 70 x 80 rectangle over the skirt, so the cuff is
        # cut back to the pale and gold that actually touches the sleeve or the
        # fist -- the frill around the wrist, the gold band above it.
        reach = union(sleeve, fist).filter(ImageFilter.MaxFilter(15))
        cuff = ImageChops.multiply(cuff, reach)
        # the frill's shadow side dips under the pale test and the fist's pale
        # rim borders the sleeve, so grow the cuff into a closed blob and let
        # the fist fill the rest of the box rather than leaving crumbs behind
        cuff = cuff.filter(ImageFilter.MaxFilter(5))
        # the gold trim is not sleeve nor cuff: any gold touching either one
        # belongs to the arm, or it stays on the dress and reads as an orange
        # bar once the sleeve swings away
        near = union(sleeve, cuff).filter(ImageFilter.MaxFilter(9))
        npx = near.load()
        trim = Image.new("L", im.size, 0)
        tpx = trim.load()
        p = im.load()
        for y in range(540, 730):
            for x in range(im.size[0]):
                if npx[x, y] and gold(*p[x, y]):
                    tpx[x, y] = 255
        fore = union(cuff, fist, trim)
        arm = union(sleeve, fore).filter(ImageFilter.MaxFilter(5))
        out[side] = {"sleeve": sleeve, "fore": fore, "arm": arm}
    return out


def blueish(r, g, b, a):
    """Colours a hidden arm may be filled with: dress navy and hair blue.

    Everything else that borders an arm hole -- the apron, its white frill,
    the lavender shading in it, the gold trim -- is a different material.

    The fill used to take any opaque pixel.  The near hand hangs in front of
    the apron, so removing it leaves a hole whose rim is apron white, and the
    nearest-neighbour fill then smeared a pale cloud out across the navy skirt.
    """
    return a > 120 and b >= r + 12 and b > 70


def patch(img, hole, src_ok=None):
    """Fill `hole` from the nearest surviving art, inside the silhouette.

    The arm holes sit against both dress navy and hair blue, so one average
    would leave a purple ring.  Nearest-neighbour keeps each side's own colour
    and a mask-limited blur melts the Voronoi creases afterwards.

    `src_ok` restricts which surviving pixels may be a source, e.g. to cloth
    and hair only (see `blueish`).
    """
    out = img.copy()
    p = out.load()
    rest = hole.copy()
    rp = rest.load()
    # every masked pixel is repainted, including the arm's own anti-aliased
    # rim: those pixels are opaque enough to survive the alpha test but still
    # carry the white cuff and the pale frill, and left alone they scatter a
    # white haze across the skirt once the arm has moved away
    holes = [(x, y) for y in range(out.height) for x in range(out.width)
             if rp[x, y]]
    # seeds are the surviving art AROUND the hole -- the hole itself is exactly
    # where the arm was, so it never has anything left to grow from
    srcs = [(x, y) for y in range(out.height) for x in range(out.width)
            if not hole.getpixel((x, y)) and p[x, y][3] > 8
            and (src_ok is None or src_ok(*p[x, y]))]
    q = deque(srcs)
    seen = set(srcs)
    while q:
        x, y = q.popleft()
        col = p[x, y]
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < out.width and 0 <= ny < out.height and (nx, ny) not in seen \
                    and rp[nx, ny]:
                p[nx, ny] = col
                seen.add((nx, ny))
                q.append((nx, ny))
    blur = out.filter(ImageFilter.GaussianBlur(4)).load()
    for x, y in holes:
        p[x, y] = blur[x, y]
    return out


def face_mask(im, cut_y, seed=(540, 470), grow=4):
    """The painted face: the skin flood plus everything it encloses.

    A colour test alone is not enough.  The eyes are blue and the lashes and
    blush are dark red, so "keep only hair" leaves a pair of eyes floating in
    the hair_back layer; dropping every non-blue pixel instead eats the pale
    hair highlights and leaves a visible seam at the collar row.

    The eyes, lashes and blush are islands inside the skin region.  Flooding
    skin and then adding everything that cannot be reached from the crop edge
    takes the whole face exactly, and a few pixels of growth take in the
    contour that bounds it.
    """
    W, H = im.size
    m = flood_mask(im, seed, is_skin)
    m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    win = Image.new("L", (W, H), 0)
    ImageDraw.Draw(win).rectangle((0, 0, W, cut_y), fill=255)
    m = ImageChops.multiply(m, win)

    inv = Image.eval(m, lambda v: 255 - v)
    ip = inv.load()
    seen = Image.new("L", (W, H), 0)
    sp = seen.load()
    q = deque()
    for x in range(W):
        for y in (0, H - 1):
            if ip[x, y] and not sp[x, y]:
                sp[x, y] = 255
                q.append((x, y))
    for y in range(H):
        for x in (0, W - 1):
            if ip[x, y] and not sp[x, y]:
                sp[x, y] = 255
                q.append((x, y))
    while q:
        x, y = q.popleft()
        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if 0 <= nx < W and 0 <= ny < H and ip[nx, ny] and not sp[nx, ny]:
                sp[nx, ny] = 255
                q.append((nx, ny))

    out = m.copy()
    op = out.load()
    for y in range(cut_y + 1):
        for x in range(W):
            if ip[x, y] and not sp[x, y]:
                op[x, y] = 255
    return out


def build(key, full=True):
    im = register(key)
    W, H = im.size
    cut_y = NECK[key]
    ap = im.getchannel("A")
    app = ap.load()

    # ---- head: the rows above the collar line, untouched
    head = Image.new("L", (W, H), 0)
    hp = head.load()
    for y in range(0, cut_y + 1):
        for x in range(W):
            if app[x, y] > 0:
                hp[x, y] = 255
    if not full:
        # only the face is needed from the head-up sheet; its arms are drawn
        # 40 px lower than the seeds the 3/4 sheet taught, and never used
        return {"head": cut(im, ImageChops.invert(head))}

    arms = arm_masks(im)
    arm_hole = union(arms["l"]["arm"], arms["r"]["arm"])

    # ---- hair_back: everything, arms patched out, the painted face dropped.
    # What is left above the collar is hair only, so a tilted head uncovers
    # hair instead of the face it was drawn with.
    back = im.copy()
    back.putalpha(ImageChops.multiply(ap, ImageChops.invert(arm_hole)))
    face = face_mask(im, cut_y)
    fp, bp = face.load(), back.load()
    for y in range(0, cut_y + 1):
        for x in range(W):
            if fp[x, y]:
                bp[x, y] = (0, 0, 0, 0)
    back = patch(back, arm_hole.copy(), src_ok=blueish)

    # ---- body: below the collar line only
    body = im.copy()
    keep = Image.new("L", (W, H), 0)
    ImageDraw.Draw(keep).rectangle((0, cut_y, W, H), fill=255)
    body.putalpha(ImageChops.multiply(ap, ImageChops.multiply(keep, ImageChops.invert(arm_hole))))
    body = patch(body, ImageChops.multiply(arm_hole, keep), src_ok=blueish)

    layers = {"hair_back": back, "body": body,
              "head": cut(im, ImageChops.invert(head))}

    # ---- arms
    for side in ("l", "r"):
        sleeve = ImageChops.multiply(arms[side]["sleeve"], ap)
        upper = Image.new("L", (W, H), 0)
        fore = Image.new("L", (W, H), 0)
        up_p, fo_p, sl_p = upper.load(), fore.load(), sleeve.load()
        ey = ELBOW_Y[side]
        for y in range(H):
            for x in range(W):
                if not sl_p[x, y]:
                    continue
                if y <= ey + 4:
                    up_p[x, y] = 255
                if y >= ey - 8:
                    fo_p[x, y] = 255
        up_m = ImageChops.multiply(upper.filter(ImageFilter.MaxFilter(3)), ap)
        fo_m = ImageChops.multiply(union(fore, arms[side]["fore"].filter(ImageFilter.MaxFilter(3))), ap)
        layers["arm_up_" + side] = cut(im, ImageChops.invert(up_m))
        layers["arm_fore_" + side] = cut(im, ImageChops.invert(fo_m))
    return layers


def rig_layers():
    """Layers for build_spine, keyed by attachment name -> (image, rect).

    The 3/4 painting supplies the whole side body; only the head and neck come
    from the head-up painting, so the skirt, apron, legs, shoes and the long
    hair never change when the drink swaps the face in.
    """
    r34 = build("r34")
    up = build("up", full=False)
    out = {}
    for name in ("hair_back", "body", "arm_up_l", "arm_fore_l",
                 "arm_up_r", "arm_fore_r"):
        out["s_" + name] = r34[name]
    out["s_head"] = up["head"]
    return {k: (v.crop(v.getchannel("A").getbbox()), v.getchannel("A").getbbox())
            for k, v in out.items()}


def preview():
    r34 = build("r34")
    up = build("up", full=False)
    both = r34["hair_back"].copy()
    both.alpha_composite(r34["body"])
    both.alpha_composite(up["head"])

    tiles = [(k, v) for k, v in r34.items()] + [("up head", up["head"]),
                                                ("swap", both)]
    sheet = Image.new("RGBA", (5 * 260, 2 * 300), (250, 250, 252, 255))
    d = ImageDraw.Draw(sheet)
    for i, (name, img) in enumerate(tiles):
        bg = Image.new("RGBA", (1024, 1024), (236, 239, 246, 255))
        bg.alpha_composite(img)
        t = bg.crop((150, 300, 800, 1000)).resize((250, 270), Image.LANCZOS)
        x = (i % 5) * 260 + 5
        y = (i // 5) * 300 + 8
        sheet.paste(t, (x, y))
        d.text((x, y + 272), name, fill=(20, 20, 30))
    sheet.convert("RGB").save(os.path.join(DEBUG, "side_layers.png"))
    print("wrote tools/_debug/side_layers.png")


if __name__ == "__main__":
    preview()
