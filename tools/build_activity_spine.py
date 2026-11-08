"""Build standalone Spine rigs for the 1-minute follow-along activity poses.

`prepare_activity_kit.py` already delivered the structural work: each mode has a
`setup.json` whose bones, slots and region attachments are fully placed (region
x/y/width/height are bone-local, exactly as the spine-godot runtime expects).
This script only does what is left for a playable rig:

  1. packs every region image referenced by the setup into one atlas PNG, and
  2. emits a self-contained `.spine-json` whose bones/slots/skins are copied
     verbatim from the setup, plus the `activity_*` animation clips.

The region attachment `path` strings (`common/hair_back`, `standing/thigh_l`, …)
are kept intact and used verbatim as atlas region names, so the setup's placement
is reproduced exactly.  Output goes to `tools/_debug/activity_spine/` for isolated
previewing (mirroring build_seated_spine / build_rest_spine); nothing here touches
the production `pet` rig.
"""
from pathlib import Path
import json
import math
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/art/activity_spine_kit_v1'
HEEL_V2_KIT = ROOT / 'assets/art/activity_spine_kit_v2'
OUT = ROOT / 'tools/_debug/activity_spine'

GUTTER = 2
ATLAS_WIDTH = 2048
CANVAS = (1024, 1024)

MODES = ('standing', 'seated')


def shelf_pack(items):
    """items: [(name, Image)] -> placements [(name, x, y, w, h)] and page size."""
    order = sorted(items, key=lambda kv: -kv[1].size[1])
    placements = []
    x, y, shelf_h = 0, 0, 0
    for name, img in order:
        w, h = img.size
        if x + w + GUTTER > ATLAS_WIDTH:
            x, y, shelf_h = 0, y + shelf_h + GUTTER, 0
        placements.append((name, x, y, w, h))
        x += w + GUTTER
        shelf_h = max(shelf_h, h)
    return placements, (ATLAS_WIDTH, y + shelf_h + GUTTER)


def compute_world(bones):
    """bone -> (x, y) in skeleton world space (y-up), summing ancestor local
    offsets.  Every activity bone has setup rotation 0, so this accumulation is
    also the bone's world transform (no rotation matrix to compose)."""
    world = {}
    for b in bones:
        x, y = b.get('x', 0.0), b.get('y', 0.0)
        if 'parent' in b:
            px, py = world[b['parent']]
            world[b['name']] = (px + x, py + y)
        else:
            world[b['name']] = (x, y)
    return world


def load_heel_v2_overrides():
    """ART-HEEL-01 (v2 redrawn front-facing heel shoes).

    Returns (region_overrides, image_overrides):
      * region_overrides[(slot, attachment)] -> the v2 region dict (x/y/width/
        height/rotation) to replace the old heel region with;
      * image_overrides[atlas path] -> Path to the v2 PNG that should be packed
        in place of the v1 `extra/heel_{l,r}.png`.

    Nothing here mutates the v1 source kit; build() applies the overrides only
    when asked (--heel-v2).
    """
    manifest = json.loads((HEEL_V2_KIT / 'ART_HEEL_01.json').read_text(encoding='utf-8'))
    region_overrides = {}
    image_overrides = {}
    for change in manifest.get('changes', []):
        region_overrides[(change['slot'], change['attachment'])] = change['region']
        image_overrides[change['path']] = HEEL_V2_KIT / change['source_png']
    return region_overrides, image_overrides


def smoothstep(a, b, v):
    if a == b:
        return 1.0 if v >= b else 0.0
    t = 0.0 if v <= a else (1.0 if v >= b else (v - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def arm_mesh(region, side, world, bone_index, grid=5.0):
    """Weighted sleeve mesh over one arm image.

    The arm PNG is a single continuous sleeve from the shoulder cap down to the
    hand, so a plain region rotates as one rigid plate and an elbow bend does
    nothing to the pixels.  Weighting it across the upper-arm / forearm / hand
    bones (with a torso blend at the shoulder cap) lets the painted sleeve fold
    at the elbow and the hand stay attached.  `region` carries the region
    attachment's x/y/width/height in the upper-arm bone's local frame, exactly
    as prepare_activity_kit placed it; the mesh reproduces that same rectangle
    at setup pose.
    """
    upper, fore, hand = 'upper_arm_%s' % side, 'forearm_%s' % side, 'hand_%s' % side
    S, E, W = world[upper], world[fore], world[hand]
    fx, fy = W[0] - E[0], W[1] - E[1]
    length = math.hypot(fx, fy)
    dx, dy = fx / length, fy / length

    def weights(wx, wy):
        # projection of the point onto the forearm axis (elbow -> wrist)
        along = (wx - E[0]) * dx + (wy - E[1]) * dy
        fore_t = smoothstep(-12.0, 16.0, along)                    # upper -> forearm
        grip_t = smoothstep(length - 18.0, length + 1.0, along)    # forearm -> hand
        root_t = 1.0 - smoothstep(10.0, 34.0, math.hypot(wx - S[0], wy - S[1]))
        return {'torso': root_t, upper: (1.0 - root_t) * (1.0 - fore_t),
                fore: (1.0 - root_t) * fore_t * (1.0 - grip_t),
                hand: (1.0 - root_t) * fore_t * grip_t}

    cx, cy = region['x'], region['y']
    w, h = region['width'], region['height']
    cols = int(math.ceil(w / grid)) + 1
    rows = int(math.ceil(h / grid)) + 1
    uvs, entries = [], []
    for j in range(rows):
        v = j / float(rows - 1)                       # 0 = sleeve top, 1 = sleeve bottom
        for i in range(cols):
            u = i / float(cols - 1)                   # 0 = left, 1 = right
            uvs.append(round(u, 6))
            uvs.append(round(v, 6))
            lx = cx + (u - 0.5) * w
            ly = cy + (0.5 - v) * h                   # local +y is up (toward the shoulder)
            wx, wy = S[0] + lx, S[1] + ly
            entry = []
            for bone, amt in sorted(weights(wx, wy).items(), key=lambda kv: -kv[1]):
                if amt <= 0.0:
                    continue
                bx, by = world[bone]
                entry.append((bone_index[bone], round(wx - bx, 3),
                              round(wy - by, 3), amt))
            entries.append(entry)

    tris = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a = j * cols + i
            tris.extend((a, a + cols, a + cols + 1, a, a + cols + 1, a + 1))

    flat = []
    for entry in entries:
        total = sum(e[3] for e in entry) or 1.0
        entry = [e for e in entry if e[3] / total > 0.008][:4]
        total = sum(e[3] for e in entry) or 1.0
        flat.append(len(entry))
        for bone, bx, by, amt in entry:
            flat.extend((bone, bx, by, round(amt / total, 4)))
    return {'type': 'mesh', 'uvs': uvs, 'triangles': tris, 'vertices': flat,
            'width': w, 'height': h}


def _zero_rows(img, from_row):
    """Blank every row from `from_row` to the bottom of the image."""
    w, h = img.size
    img.paste(Image.new('RGBA', (w, h - from_row), (0, 0, 0, 0)), (0, from_row))


def _taper_sock(img, start_row, end_row, target_width):
    """Narrow the sock silhouette from its natural width at `start_row` to
    `target_width` at `end_row` (symmetric), so the leg sock meets the narrower
    v2 heel-shoe sock top without a width step when the heel raises."""
    a = img.getchannel('A')
    W = img.size[0]
    for r in range(start_row, end_row + 1):
        xs = [x for x in range(W) if a.getpixel((x, r)) > 0]
        if not xs:
            continue
        xmin, xmax = min(xs), max(xs)
        center = (xmin + xmax) / 2.0
        t = (r - start_row) / float(end_row - start_row)
        w = (xmax - xmin + 1) + (target_width - (xmax - xmin + 1)) * t
        lo = int(round(center - w / 2.0))
        hi = int(round(center + w / 2.0))
        for x in range(0, lo):
            img.putpixel((x, r), (0, 0, 0, 0))
        for x in range(hi + 1, W):
            img.putpixel((x, r), (0, 0, 0, 0))


def leg_mesh_images(side):
    """Normal and heel-raise textures for one continuous leg mesh.

    Both come from `leg_{side}_full` (the single continuous leg drawing), so the
    knee has no slice feather to split open.  Only the rows below the sock are
    blanked: normal keeps the sock to row 336, the heel raise cuts it to row 300
    (exactly how calf_heel_{side} shortened the sock) and tapers the last rows
    toward the v2 heel-shoe sock width so the swap doesn't show a width step.
    Both stay 157x440 so the packer's resize-to-region keeps the same scale as
    every other leg part.
    """
    full = Image.open(SRC / 'parts' / 'standing' / ('leg_%s_full.png' % side)).convert('RGBA')
    norm = full.copy()
    heel = full.copy()
    _zero_rows(norm, 336)
    _zero_rows(heel, 300)
    _taper_sock(heel, 270, 300, 81)
    return norm, heel


def leg_mesh(region, side, world, bone_index, grid=5.0):
    """Weighted continuous thigh-knee-calf mesh over the full-leg mother asset.

    thigh_l/calf_l are two rigid 157x440 plates whose painted overlap (source
    rows 136-165) feathers each slice toward the knee joint; when the knee bends
    they rotate apart and that feather splits into a visible cut edge.  This mesh
    uses the single continuous drawing instead, weighted across the thigh (top)
    and calf (bottom) bones so the knee folds smoothly.  `region` is the old
    thigh region (x=0, y=-100, width/height = the full leg box), so the mesh
    occupies exactly the space the two plates used to.
    """
    thigh, calf = 'thigh_%s' % side, 'calf_%s' % side
    S = world[thigh]                       # slot bone == thigh (hip end of leg)
    cx, cy = region['x'], region['y']
    w, h = region['width'], region['height']
    cols = int(math.ceil(w / grid)) + 1
    rows = int(math.ceil(h / grid)) + 1

    # Knee blend in thigh-local y (y-up).  The knee (calf bone) sits at (0, -63)
    # in the thigh frame; the painted thigh/calf overlap is local y ~-56..-71.
    # The blend band is sized to the painted leg width (~47 units) so the fold
    # rounds like a knee cap instead of pinching into a V on the concave side;
    # it stays centered on the calf-bone pivot (the actual joint), and the mesh
    # rows already run across the leg (perpendicular to the vertical thigh/calf
    # axis), so the fold follows the joint rather than smearing diagonally.
    knee_hi = -40.0   # above -> thigh only
    knee_lo = -86.0   # below -> calf only

    art_thigh = 'art_knee_thigh_%s' % side
    art_calf = 'art_knee_calf_%s' % side

    def weights(ly):
        t = smoothstep(knee_lo, knee_hi, ly)
        return {thigh: t, calf: 1.0 - t}

    def knee_mask(lx, ly):
        # Outer-half only, fading out away from the knee pivot (ly == -63).  Each
        # corrective bone sits at the same setup position as its parent, so this
        # weight split is a no-op at the neutral pose; it just hands the animation
        # track a lever to push the outer knee edge outward during flexion.
        outside = -lx if side == 'l' else lx
        return (smoothstep(5.0, 22.0, outside)
                * (1.0 - smoothstep(5.0, 32.0, abs(ly + 63.0))))

    uvs, entries = [], []
    for j in range(rows):
        v = j / float(rows - 1)                      # 0 = leg top, 1 = leg bottom
        for i in range(cols):
            u = i / float(cols - 1)                  # 0 = left, 1 = right
            uvs.append(round(u, 6))
            uvs.append(round(v, 6))
            lx = cx + (u - 0.5) * w
            ly = cy + (0.5 - v) * h                  # local +y is up (toward hip)
            wx, wy = S[0] + lx, S[1] + ly
            mask = knee_mask(lx, ly)
            entry = []
            for bone, amt in sorted(weights(ly).items(), key=lambda kv: -kv[1]):
                if amt <= 0.0:
                    continue
                bx, by = world[bone]
                stay, push = amt * (1.0 - mask), amt * mask
                if stay > 1e-7:
                    entry.append((bone_index[bone], round(wx - bx, 3),
                                  round(wy - by, 3), stay))
                if push > 1e-7:
                    art = art_thigh if bone == thigh else art_calf
                    entry.append((bone_index[art], round(wx - bx, 3),
                                  round(wy - by, 3), push))
            entries.append(entry)

    tris = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a = j * cols + i
            tris.extend((a, a + cols, a + cols + 1, a, a + cols + 1, a + 1))

    flat = []
    for entry in entries:
        total = sum(e[3] for e in entry) or 1.0
        entry = [e for e in entry if e[3] / total > 0.008][:4]
        total = sum(e[3] for e in entry) or 1.0
        flat.append(len(entry))
        for bone, bx, by, amt in entry:
            flat.extend((bone, bx, by, round(amt / total, 4)))
    return {'type': 'mesh', 'uvs': uvs, 'triangles': tris, 'vertices': flat,
            'width': w, 'height': h}


def _ankle_t(wy):
    """0 = above the ankle (calf-driven), 1 = below (foot-driven).

    Mirrors tools/probe_activity_sock_join.py: screen y = -wy, so the band
    858..895 in screen space (ankle -> toward the sole) maps to world y
    -858 .. -895.  At the neutral pose this split is a no-op because calf and
    foot are rigidly parented and the weights sum to 1; it only folds pixels
    when the foot translates relative to the calf (toe-fixed heel raise).
    """
    return smoothstep(858.0, 895.0, -wy)


def _add_ankle_weights(flat, names, world, bone_index, side):
    """Split the ankle rows of an already-flattened leg mesh toward the foot.

    `flat` is the spine vertex encoding `[count, bone, x, y, weight, ...]`.
    Every entry keeps its original bone for the calf side and hands an
    ankle-blend fraction to the foot bone (offset relative to the foot), so the
    sock hem and the shoe move as one continuous skin when the ankle folds.
    """
    foot = bone_index['foot_%s' % side]
    fx, fy = world['foot_%s' % side]
    out = []
    i = 0
    while i < len(flat):
        count = int(flat[i])
        i += 1
        entries = []
        for _ in range(count):
            bi, x, y, w = flat[i], flat[i + 1], flat[i + 2], flat[i + 3]
            i += 4
            bx, by = world[names[int(bi)]]
            wx, wy = bx + x, by + y
            t = _ankle_t(wy)
            stay = w * (1.0 - t)
            push = w * t
            if stay > 1e-8:
                entries.append((bi, x, y, stay))
            if push > 1e-8:
                entries.append((foot, wx - fx, wy - fy, push))
        total = sum(e[3] for e in entries) or 1.0
        entries = [e for e in entries if e[3] / total > 0.008][:4]
        total = sum(e[3] for e in entries) or 1.0
        out.append(len(entries))
        for bi, x, y, w in entries:
            out.extend((bi, x, y, round(w / total, 4)))
    return out


def shoe_mesh(region, side, world, bone_index, grid=5.0):
    """Weighted shoe mesh over the ordinary shoe artwork.

    The shoe PNG is one tall image whose upper rows are the sock overlap and
    whose lower rows are the sole.  Weighting it across calf (above the ankle)
    and foot (below) lets a small toe-fixed heel raise fold the ankle
    continuously instead of swapping to a differently-coloured v2 heel plate.
    `region` carries the ordinary shoe region x/y/width/height in the foot
    bone's local frame, exactly as prepare_activity_kit placed it.
    """
    calf, foot = 'calf_%s' % side, 'foot_%s' % side
    cx, cy = region['x'], region['y']
    w, h = region['width'], region['height']
    cols = int(math.ceil(w / grid)) + 1
    rows = int(math.ceil(h / grid)) + 1
    uvs, entries = [], []
    for j in range(rows):
        v = j / float(rows - 1)                       # 0 = top (sock), 1 = bottom (sole)
        for i in range(cols):
            u = i / float(cols - 1)
            uvs.append(round(u, 6))
            uvs.append(round(v, 6))
            lx = cx + (u - 0.5) * w
            ly = cy + (0.5 - v) * h                   # local +y is up (toward the ankle)
            wx, wy = world[foot][0] + lx, world[foot][1] + ly
            t = _ankle_t(wy)
            entry = []
            for bone, amt in ((calf, 1.0 - t), (foot, t)):
                if amt <= 1e-8:
                    continue
                bx, by = world[bone]
                entry.append((bone_index[bone], round(wx - bx, 3),
                              round(wy - by, 3), amt))
            entries.append(entry)

    tris = []
    for j in range(rows - 1):
        for i in range(cols - 1):
            a = j * cols + i
            tris.extend((a, a + cols, a + cols + 1, a, a + cols + 1, a + 1))

    flat = []
    for entry in entries:
        total = sum(e[3] for e in entry) or 1.0
        entry = [e for e in entry if e[3] / total > 0.008][:4]
        total = sum(e[3] for e in entry) or 1.0
        flat.append(len(entry))
        for bone, bx, by, amt in entry:
            flat.extend((bone, bx, by, round(amt / total, 4)))
    return {'type': 'mesh', 'uvs': uvs, 'triangles': tris, 'vertices': flat,
            'width': w, 'height': h}


def build(mode: str, heel_v2: bool = False, ankle_continuous: bool = False):
    setup = json.loads((SRC / mode / 'setup.json').read_text(encoding='utf-8'))
    # Pose-driven knee-outline corrective controls (see KNEE_CORRECTIVE_HANDOFF.md):
    # children of thigh/calf at zero setup offset, used by leg_mesh() to push the
    # outer-half knee vertices outward during flexion so the bend doesn't pinch.
    if mode == 'standing':
        for side in ('l', 'r'):
            for parent in ('thigh_%s' % side, 'calf_%s' % side):
                setup['bones'].append({'name': 'art_knee_%s' % parent, 'parent': parent})
    world = compute_world(setup['bones'])
    bone_index = {b['name']: i for i, b in enumerate(setup['bones'])}

    region_overrides, image_overrides = {}, {}
    if heel_v2:
        region_overrides, image_overrides = load_heel_v2_overrides()

    # Round every region's width/height to integer atlas cells (avoids sub-pixel
    # resampling against assembled.png), and decide which arm attachments become
    # weighted meshes.  A mesh has no `path`, so spine-godot resolves its atlas
    # region by the attachment name -- the arm regions are therefore keyed by
    # `arm_l`/`arm_r` while every region attachment keeps its full `path`.
    arm_slots = {'arm_l', 'arm_r'}
    atlas_sources = {}   # atlas region name -> parts-relative PNG path
    atlas_sizes = {}     # atlas region name -> (rounded width, height)

    for skin in setup['skins']:
        for slot_name, variants in skin['attachments'].items():
            for att_name, att in variants.items():
                if (slot_name, att_name) in region_overrides:
                    att.update(region_overrides[(slot_name, att_name)])
                w, h = round(att['width']), round(att['height'])
                att['width'], att['height'] = w, h
                if slot_name in arm_slots and att_name in arm_slots:
                    atlas_sources[att_name] = att['path']
                    atlas_sizes[att_name] = (w, h)
                else:
                    atlas_sources[att['path']] = att['path']
                    atlas_sizes[att['path']] = (w, h)

    # Swap the two arm regions for weighted sleeve meshes.
    for skin in setup['skins']:
        for slot_name, variants in skin['attachments'].items():
            for att_name, att in variants.items():
                if slot_name in arm_slots and att_name in arm_slots:
                    variants[att_name] = arm_mesh(att, att_name[-1], world, bone_index)

    # Restructure the legs (standing only): replace the two rigid thigh/calf
    # plates with one continuous thigh-knee-calf mesh over the full-leg mother
    # asset, keyed by attachment name so spine-godot resolves the atlas region
    # the same way the arm meshes do.  The shoe slot stays independent so the
    # shoe<->heel swap keeps working; the calf slot and its calf/calf_heel
    # regions are dropped (the heel variant is now `leg_heel_*`).
    leg_composites = {}
    if mode == 'standing':
        names = [b['name'] for b in setup['bones']]
        for side in ('l', 'r'):
            tslot, cslot = 'thigh_%s' % side, 'calf_%s' % side
            for skin in setup['skins']:
                atts = skin['attachments']
                region = atts[tslot][tslot]          # full-leg box (rounded already)
                leg = leg_mesh(region, side, world, bone_index)
                if ankle_continuous:
                    # Same artwork + continuous ankle skinning for both variants:
                    # leg_heel reuses leg (no cut sock / taper) and the ankle rows
                    # hand off to the foot so the hem follows the shoe.
                    leg = {'type': 'mesh', 'uvs': leg['uvs'],
                           'triangles': leg['triangles'],
                           'vertices': _add_ankle_weights(leg['vertices'], names,
                                                          world, bone_index, side),
                           'width': leg['width'], 'height': leg['height']}
                atts[tslot] = {
                    'leg_%s' % side: leg,
                    'leg_heel_%s' % side: leg,
                }
                atts.pop(cslot, None)
            norm, heel = leg_mesh_images(side)
            if ankle_continuous:
                heel = norm.copy()                   # same artwork, no cut/taper
            leg_composites['leg_%s' % side] = norm
            leg_composites['leg_heel_%s' % side] = heel
            for name in ('leg_%s' % side, 'leg_heel_%s' % side):
                atlas_sources[name] = name
                atlas_sizes[name] = (round(region['width']), round(region['height']))
        if ankle_continuous:
            # Shoe<->heel become one continuous ankle mesh over the ordinary
            # shoe artwork; the heel no longer swaps to a differently-coloured
            # v2 plate, so the swap is visually a no-op at any shared pose.
            for side in ('l', 'r'):
                sslot = 'shoe_%s' % side
                for skin in setup['skins']:
                    atts = skin['attachments']
                    shoe_region = atts[sslot]['shoe_%s' % side]
                    mesh = shoe_mesh(shoe_region, side, world, bone_index)
                    atts[sslot] = {
                        'shoe_%s' % side: mesh,
                        'heel_%s' % side: mesh,
                    }
                # Both atlas aliases reuse the ordinary shoe artwork (82x230);
                # drop the old extra/heel_* and standing/shoe_* region entries.
                for alias in ('shoe_%s' % side, 'heel_%s' % side):
                    atlas_sources[alias] = 'standing/shoe_%s' % side
                    atlas_sizes[alias] = (round(shoe_region['width']),
                                          round(shoe_region['height']))
                atlas_sources.pop('extra/heel_%s' % side, None)
                atlas_sizes.pop('extra/heel_%s' % side, None)
                atlas_sources.pop('standing/shoe_%s' % side, None)
                atlas_sizes.pop('standing/shoe_%s' % side, None)
        setup['slots'] = [s for s in setup['slots']
                          if s['name'] not in ('calf_l', 'calf_r')]
        for s in setup['slots']:
            if s['name'] == 'thigh_l':
                s['attachment'] = 'leg_l'
            elif s['name'] == 'thigh_r':
                s['attachment'] = 'leg_r'
        # Drop the now-unreferenced thigh/calf/calf_heel atlas entries.
        for name in ('standing/thigh_l', 'standing/calf_l', 'standing/calf_heel_l',
                     'standing/thigh_r', 'standing/calf_r', 'standing/calf_heel_r'):
            atlas_sources.pop(name, None)
            atlas_sizes.pop(name, None)

    # ---- pack (pre-scaled to each region's own width/height) -----------------
    scaled = {}
    for name, src_path in atlas_sources.items():
        if name in leg_composites:
            img = leg_composites[name]
        else:
            img_path = image_overrides.get(src_path, SRC / 'parts' / (src_path + '.png'))
            img = Image.open(img_path).convert('RGBA')
        if img.size != atlas_sizes[name]:
            img = img.resize(atlas_sizes[name], Image.Resampling.LANCZOS)
        scaled[name] = img

    placements, page_size = shelf_pack([(p, scaled[p]) for p in scaled])
    page = Image.new('RGBA', page_size, (0, 0, 0, 0))
    region_rects = {}
    for name, x, y, w, h in placements:
        page.paste(scaled[name], (x, y))
        region_rects[name] = (x, y, w, h)

    base = 'activity_%s' % mode
    page.save(OUT / (base + '.png'))

    # ---- atlas --------------------------------------------------------------
    atlas = [base + '.png',
             'size: %d,%d' % page_size,
             'format: RGBA8888',
             'filter: Linear,Linear',
             'repeat: none']
    for name in atlas_sizes:
        x, y, w, h = region_rects[name]
        atlas += [name,
                  '  rotate: false',
                  '  xy: %d, %d' % (x, y),
                  '  size: %d, %d' % (w, h),
                  '  orig: %d, %d' % (w, h),
                  '  offset: 0, 0',
                  '  index: -1']
    (OUT / (base + '.atlas')).write_text('\n'.join(atlas) + '\n', encoding='utf-8', newline='\n')

    # ---- skeleton: bones/slots/skins, images now local ----------------------
    skeleton = {
        'skeleton': dict(setup['skeleton'], images='./', audio=''),
        'bones': setup['bones'],
        'slots': setup['slots'],
        'skins': setup['skins'],
        'animations': build_animations(mode, setup),
    }
    (OUT / (base + '.spine-json')).write_text(json.dumps(skeleton, indent=2), encoding='utf-8')

    n_mesh = sum(1 for s in setup['skins'] for v in s['attachments'].values()
                 for a in v.values() if a['type'] == 'mesh')
    print('%s: page %s, %d regions (%d meshes)' % (base, page_size, len(atlas_sizes), n_mesh))
    for name in atlas_sizes:
        x, y, w, h = region_rects[name]
        print('  %-24s atlas %4dx%-4d at (%4d,%4d)' % (name, w, h, x, y))


# ---------------------------------------------------------------------------
# Animation authoring.  Spine conventions (verified against the runtime):
#   * rotate keys are ABSOLUTE local degrees (all setup bones have rotation 0,
#     so a keyframe value is the delta from the setup pose).
#   * translate keys are ABSOLUTE local x/y, so they must include the bone's own
#     setup offset.  `trans()` adds that offset for us from a delta.
#   * linear interpolation between keyframes (no stepped/hold curves yet).
# ---------------------------------------------------------------------------


def _rot(keys):
    """keys: [(time, deg)] -> rotate track."""
    return [{'time': round(t, 3), 'value': v} for t, v in keys]


def _trans(keys):
    """keys: [(time, dx, dy)] -> translate track.  The spine-godot runtime treats
    translate keyframes as deltas added to the bone's setup position (confirmed
    against the production `tr()` and a torso-probe), so the delta is written
    directly, never setup + delta."""
    return [{'time': round(t, 3), 'x': round(dx, 3), 'y': round(dy, 3)}
            for t, dx, dy in keys]


def _slot(keys):
    """keys: [(time, attachment_name)] -> slot attachment track."""
    return [{'time': round(t, 3), 'name': name} for t, name in keys]


def _knee_corrective(bones, duration):
    """Pose-driven knee-outline corrective tracks for the art_knee_* control bones.

    Mirrors tools/probe_activity_knee_corrective.py: the push-out amplitude is 17
    units at full calf flexion (35 deg), scaled smoothly, and rotated into the
    parent bone's local frame so the screen-horizontal push stays horizontal.
    Returns {bone_name: {'translate': keys}} to merge into a clip's bones."""
    def sample(keys, t):
        for first, last in zip(keys, keys[1:]):
            if first['time'] <= t <= last['time']:
                span = last['time'] - first['time']
                u = (t - first['time']) / span if span else 0.0
                return first['value'] * (1.0 - u) + last['value'] * u
        return keys[-1]['value'] if keys else 0.0

    def rot(name):
        return bones.get(name, {}).get('rotate', [{'time': 0, 'value': 0}])

    out = {}
    times = [round(i / 20.0, 3) for i in range(int(round(duration * 20)) + 1)]
    for side in ('l', 'r'):
        thigh, calf = rot('thigh_%s' % side), rot('calf_%s' % side)
        for part in ('thigh', 'calf'):
            keys = []
            for t in times:
                ta, ca = sample(thigh, t), sample(calf, t)
                amplitude = 17.0 * min(abs(ca) / 35.0, 1.0) ** 1.4
                dx = -amplitude if side == 'l' else amplitude
                theta = math.radians(ta + (ca if part == 'calf' else 0.0))
                keys.append({'time': t,
                             'x': round(dx * math.cos(theta), 3),
                             'y': round(-dx * math.sin(theta), 3)})
            out['art_knee_%s_%s' % (part, side)] = {'translate': keys}
    return out


def _standing_anims(pos):
    """Shared standing clips.  Angles are a conservative first pass; the sign
    (which way a foot/arm swings) may need flipping after visual review."""

    def neutral():
        return {'bones': {
            'torso': {'translate': _trans(
                [(0, 0, 0), (0.5, 0, 1.2), (1.0, 0, 1.2), (1.6, 0, 0), (2.0, 0, 0)])},
            'head': {'rotate': _rot([(0, 0), (0.6, 0.5), (1.4, -0.5), (2.0, 0)])},
        }}

    def ready():
        # 0-1.0 s raise the right arm into the wave target, 1.0-1.5 s hold the
        # invite, 1.5-2.5 s lower it, then stand with a light breathe to 10 s.
        # The target pose fixes the old -125 deg whole-arm swing that hid the arm
        # in the hair: the shoulder stays put, the elbow abducts OUTWARD (+75 deg
        # upper arm), and the forearm bends (+45 deg) so the hand lands beside the
        # right side of the face instead of behind the head.  FK (y-up, CCW+):
        # shoulder (572,457) -> elbow (663,452) -> wrist (705,401), head x[263,761].
        return {'bones': {
            'upper_arm_r': {'rotate': _rot([(0, 0), (1.0, 75), (1.5, 75), (2.5, 0), (10, 0)])},
            'forearm_r': {'rotate': _rot([(0, 0), (1.0, 45), (1.5, 45), (2.5, 0), (10, 0)])},
            'upper_arm_l': {'rotate': _rot([(0, 0), (1.0, -8), (1.5, -8), (2.5, 0), (10, 0)])},
            'head': {'rotate': _rot([(0, 0), (1.0, 3), (1.5, 3), (2.5, -1), (10, 0)])},
            'torso': {'translate': _trans(
                [(0, 0, 0), (1.0, 0, 1.5), (2.5, 0, 1.0), (5, 0, 1.4), (8, 0, 0), (10, 0, 0)])},
        }}

    def march_cycle():
        # 2 s: left foot low-lift (0-0.5) -> settle (0.5-1.0) -> right foot
        # low-lift (1.0-1.5) -> settle (1.5-2.0).  Uses the verified probe-step
        # low-sway trajectory (thigh +20 / calf -35 and its mirror) instead of
        # the old rigid-plate lateral swing; the continuous leg mesh now folds
        # the knee instead of splitting the thigh/calf plates.
        bones = {
            'thigh_l': {'rotate': _rot([(0, 0), (0.5, 20), (1.0, 0), (2, 0)])},
            'calf_l': {'rotate': _rot([(0, 0), (0.5, -35), (1.0, 0), (2, 0)])},
            'thigh_r': {'rotate': _rot([(0, 0), (1.0, 0), (1.5, -20), (2.0, 0), (2, 0)])},
            'calf_r': {'rotate': _rot([(0, 0), (1.0, 0), (1.5, 35), (2.0, 0), (2, 0)])},
            'upper_arm_l': {'rotate': _rot([(0, 0), (0.5, 5), (1.0, 0), (1.5, -5), (2.0, 0), (2, 0)])},
            'upper_arm_r': {'rotate': _rot([(0, 0), (0.5, -5), (1.0, 0), (1.5, 5), (2.0, 0), (2, 0)])},
            'torso': {'rotate': _rot([(0, 0), (0.5, 1), (1.0, 0), (1.5, -1), (2, 0)])},
        }
        bones.update(_knee_corrective(bones, 2.0))
        return {'bones': bones}

    def heel_cycle():
        # 4 s: 1 s rise onto the toes -> 1 s hold -> 1.5 s lower -> 0.5 s settle.
        # Toe-fixed raise (probe 3 mechanism, which passed): the hip rises and the
        # feet get an equal-and-opposite translate so the toe contact stays planted
        # at the ground; the raised heel read comes from swapping leg->leg_heel
        # and shoe->heel at the peak, not from foot rotation (the ankle sits almost
        # directly above the toe, so rotating only swings the ankle sideways -- the
        # exact sway this loop must avoid).  The v2 heel art keeps the front-facing
        # shoe orientation, so this matches its ground registration.
        rise = 5.0
        return {
            'bones': {
                'hip': {'translate': _trans(
                    [(0, 0, 0), (1.0, 0, rise), (2.0, 0, rise), (3.5, 0, 0), (4, 0, 0)])},
                'foot_l': {'translate': _trans(
                    [(0, 0, 0), (1.0, 0, -rise), (2.0, 0, -rise), (3.5, 0, 0), (4, 0, 0)])},
                'foot_r': {'translate': _trans(
                    [(0, 0, 0), (1.0, 0, -rise), (2.0, 0, -rise), (3.5, 0, 0), (4, 0, 0)])},
            },
            'slots': {
                'thigh_l': {'attachment': _slot(
                    [(0, 'leg_l'), (1.0, 'leg_heel_l'), (2.0, 'leg_heel_l'), (3.5, 'leg_l'), (4, 'leg_l')])},
                'shoe_l': {'attachment': _slot(
                    [(0, 'shoe_l'), (1.0, 'heel_l'), (2.0, 'heel_l'), (3.5, 'shoe_l'), (4, 'shoe_l')])},
                'thigh_r': {'attachment': _slot(
                    [(0, 'leg_r'), (1.0, 'leg_heel_r'), (2.0, 'leg_heel_r'), (3.5, 'leg_r'), (4, 'leg_r')])},
                'shoe_r': {'attachment': _slot(
                    [(0, 'shoe_r'), (1.0, 'heel_r'), (2.0, 'heel_r'), (3.5, 'shoe_r'), (4, 'shoe_r')])},
            },
        }

    def relax():
        # 5 s base fragment: light breathe + a blink, hands low and still.
        return {'bones': {
            'torso': {'translate': _trans(
                [(0, 0, 0), (1.2, 0, 1.3), (2.4, 0, 1.3), (4.0, 0, 0), (5, 0, 0)])},
            'head': {'rotate': _rot([(0, 0), (1.2, 0.6), (2.4, -0.6), (4.0, 0), (5, 0)])},
        }}

    def probe_elbow():
        # Probe 1a: upper arm fixed, bend only the forearm.  The sleeve's lower
        # half must fold around the elbow with the painted pixels -- no naked
        # forearm, no seam -- while the shoulder cap stays put.
        return {'bones': {
            'forearm_l': {'rotate': _rot([(0, 0), (0.5, -80), (1.0, -80), (1.5, 0), (2.0, 0)])},
            'forearm_r': {'rotate': _rot([(0, 0), (0.5, 80), (1.0, 80), (1.5, 0), (2.0, 0)])},
        }}

    def probe_wrist():
        # Probe 1b: elbow fixed, move only the wrist/hand around the wrist pivot.
        return {'bones': {
            'hand_l': {'rotate': _rot([(0, 0), (0.5, -40), (1.0, -40), (1.5, 0), (2.0, 0)])},
            'hand_r': {'rotate': _rot([(0, 0), (0.5, 40), (1.0, 40), (1.5, 0), (2.0, 0)])},
        }}

    def probe_step():
        # Probe 2: left foot low-lift while the right (support) foot keeps every
        # contact point fixed.  thigh_l lifts the knee and calf_l bends so the
        # heel tucks toward the thigh; the foot comes up with almost no sideways
        # sway (FK search: thigh +20 / calf -35 -> ~6 px lift, ~0.2 px sway).
        # The right leg and upper body get no keyframes at all.
        bones = {
            'thigh_l': {'rotate': _rot([(0, 0), (0.5, 20), (1.0, 20), (1.5, 0), (2.0, 0)])},
            'calf_l': {'rotate': _rot([(0, 0), (0.5, -35), (1.0, -35), (1.5, 0), (2.0, 0)])},
        }
        bones.update(_knee_corrective(bones, 2.0))
        return {'bones': bones}

    def probe_toe():
        # Probe 3: toe-fixed heel raise.  The body rises 5 px onto the toes while
        # both toe contact points stay planted.  The foot bone is the ankle, so
        # the feet get an equal-and-opposite translate to cancel the body rise and
        # hold the shoe/heel contact at the ground; no foot rotation (rotating the
        # ankle about a toe that sits almost directly below it only swings the
        # ankle sideways, which is the sway this probe must avoid).  The raised-heel
        # read comes from swapping leg_l->leg_heel_l and shoe_l->heel_l in at the
        # peak, not from foot rotation.
        rise = 5.0
        return {
            'bones': {
                'hip': {'translate': _trans(
                    [(0, 0, 0), (0.5, 0, rise), (1.0, 0, rise), (1.5, 0, 0), (2.0, 0, 0)])},
                'foot_l': {'translate': _trans(
                    [(0, 0, 0), (0.5, 0, -rise), (1.0, 0, -rise), (1.5, 0, 0), (2.0, 0, 0)])},
                'foot_r': {'translate': _trans(
                    [(0, 0, 0), (0.5, 0, -rise), (1.0, 0, -rise), (1.5, 0, 0), (2.0, 0, 0)])},
            },
            'slots': {
                'thigh_l': {'attachment': _slot(
                    [(0, 'leg_l'), (0.5, 'leg_heel_l'), (1.5, 'leg_l')])},
                'shoe_l': {'attachment': _slot(
                    [(0, 'shoe_l'), (0.5, 'heel_l'), (1.5, 'shoe_l')])},
                'thigh_r': {'attachment': _slot(
                    [(0, 'leg_r'), (0.5, 'leg_heel_r'), (1.5, 'leg_r')])},
                'shoe_r': {'attachment': _slot(
                    [(0, 'shoe_r'), (0.5, 'heel_r'), (1.5, 'shoe_r')])},
            },
        }

    return {
        'activity_neutral': neutral(),
        'activity_ready': ready(),
        'activity_march_cycle': march_cycle(),
        'activity_heel_cycle': heel_cycle(),
        'activity_relax': relax(),
        'activity_probe_elbow': probe_elbow(),
        'activity_probe_wrist': probe_wrist(),
        'activity_probe_step': probe_step(),
        'activity_probe_toe': probe_toe(),
    }


def build_animations(mode: str, setup: dict) -> dict:
    bones = {b['name']: b for b in setup['bones']}

    def pos(name):
        b = bones[name]
        return (b.get('x', 0.0), b.get('y', 0.0))

    if mode == 'standing':
        return _standing_anims(pos)
    # Seated clips come after the standing set A is accepted.
    return {}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    heel_v2 = '--heel-v2' in sys.argv
    ankle_continuous = '--ankle-continuous' in sys.argv
    for mode in MODES:
        build(mode, heel_v2=heel_v2, ankle_continuous=ankle_continuous)
    flags = []
    if heel_v2:
        flags.append('heel v2')
    if ankle_continuous:
        flags.append('ankle continuous')
    print('activity rigs ->', OUT, '(' + ', '.join(flags) + ')' if flags else '(v1 heel)')


if __name__ == '__main__':
    main()
