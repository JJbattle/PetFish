"""Build a standalone Spine rig for the side-lying "hug whale" rest pose.

Reads the six `assets/art/rest_whale_v1/` attachments and their static assembly
manifest (`assembly.json`), packs them into one atlas, and emits a Spine 4.2
JSON carrying a single `rest_whale_loop` breathing cycle.

This rig is deliberately separate from the production `pet` rig: it does not
read or write `game/assets/pet_spine/` and is only meant for isolated previewing
until the pose is accepted and registered.

Static assembly contract
------------------------
The rig must reproduce `assets/art/rest_whale_v1/assembled.png` exactly.  Each
piece is scaled by its manifest `scale`, rotated about its `pivot` by `-angle`
(screen angles are clockwise, Spine angles are counter-clockwise), and its pivot
is placed at `position` (canvas top-left origin, +y down).

Scale is baked into the atlas (each piece is pre-resized before packing), while
rotation stays on the bone.  Verified empirically against the spine-godot
runtime (tools/region_probe.py): a region attachment's `(x, y)` is the image
**center** in the bone's local frame (+y up), which lands at `(x, -y)` after the
runtime's y-negation.  To land the piece's pivot on the bone origin we set::

    x = (W/2 - px) * s
    y = (py - H/2) * s      (px, py = pivot in the source PNG, W/H = its size)

Breathing cycle (`rest_whale_loop`, 4.8 s)
------------------------------------------
Small whole-body motion only: `rest_body` (which carries head/arms/whale as
children) rises and falls ~2.5 px while `head_sleep` sways ~0.6 degrees.  The
pillow is a child of `root` and stays fixed.  No mesh weights, no per-arm motion
-- exactly the first milestone in SPINE_REST_HANDOFF.md.
"""
from pathlib import Path
import json

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/art/rest_whale_v1'
OUT = ROOT / 'tools/_debug/rest_spine'

GUTTER = 2
ATLAS_WIDTH = 2048

# name -> (pivot, position, scale, angle) from assembly.json draw order.
# Draw order (back to front): pillow, body, head, far arm, whale, near arm.
ASSEMBLY = [
    ('pillow',         (12, 12),    (160, 390), 1.10,   0),
    ('body_legs_tail', (12, 12),    (480, 380), 0.90,   0),
    ('head_sleep',     (322, 391),  (536, 466), 1.00,   0),
    ('arm_far',        (257, 57),   (604, 520), 0.62, -10),
    ('whale',          (0, 0),      (420, 550), 0.64,   0),
    ('arm_near',       (239, 70),   (606, 475), 0.65,  20),
]

BODY = 'body_legs_tail'


def breathe() -> dict:
    """`rest_whale_loop` keyframes.  Spine space: +y up, +rotation counter-clockwise."""
    return {
        'rest_body': {
            'translate': [
                {'time': 0.0, 'x': 0.0, 'y': 0.0},
                {'time': 1.6, 'x': 0.0, 'y': 2.5},
                {'time': 2.2, 'x': 0.0, 'y': 2.5},
                {'time': 4.4, 'x': 0.0, 'y': 0.0},
                {'time': 4.8, 'x': 0.0, 'y': 0.0},
            ],
        },
        'head_sleep': {
            'rotate': [
                {'time': 0.0, 'value': 0.0},
                {'time': 1.6, 'value': 0.6},
                {'time': 2.2, 'value': 0.6},
                {'time': 4.4, 'value': -0.6},
                {'time': 4.8, 'value': 0.0},
            ],
        },
    }


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


def build():
    OUT.mkdir(parents=True, exist_ok=True)

    # ---- pre-scale each piece and pack --------------------------------------
    scaled = {}
    for name, pivot, position, scale, angle in ASSEMBLY:
        img = Image.open(SRC / (name + '.png')).convert('RGBA')
        w, h = img.size
        if scale != 1.0:
            img = img.resize((round(w * scale), round(h * scale)), Image.Resampling.LANCZOS)
        scaled[name] = img

    placements, page_size = shelf_pack([(n, scaled[n]) for n, *_ in ASSEMBLY])
    page = Image.new('RGBA', page_size, (0, 0, 0, 0))
    region_rects = {}
    for name, x, y, w, h in placements:
        page.paste(scaled[name], (x, y))
        region_rects[name] = (x, y, w, h)
    page.save(OUT / 'rest.png')

    # ---- atlas --------------------------------------------------------------
    atlas = ['rest.png',
             'size: %d,%d' % page_size,
             'format: RGBA8888',
             'filter: Linear,Linear',
             'repeat: none']
    for name, _pivot, _pos, _scale, _angle in ASSEMBLY:
        x, y, w, h = region_rects[name]
        atlas += [name,
                  '  rotate: false',
                  '  xy: %d, %d' % (x, y),
                  '  size: %d, %d' % (w, h),
                  '  orig: %d, %d' % (w, h),
                  '  offset: 0, 0',
                  '  index: -1']
    (OUT / 'rest.atlas').write_text('\n'.join(atlas) + '\n', encoding='utf-8', newline='\n')

    # ---- skeleton -----------------------------------------------------------
    by_name = {row[0]: row for row in ASSEMBLY}
    body_pos = by_name[BODY][2]
    bones = [{'name': 'root'}]
    slots = []
    skins = {'default': {}}
    for name, pivot, position, scale, angle in ASSEMBLY:
        parent = 'root' if name in ('pillow', BODY, 'head_sleep') else 'rest_body'
        bone_name = 'rest_body' if name == BODY else name
        bx, by = position
        if parent == 'rest_body':
            bx -= body_pos[0]
            by -= body_pos[1]
        bones.append({'name': bone_name, 'parent': parent,
                      'x': round(bx, 3), 'y': round(-by, 3),
                      'rotation': round(-angle, 3)})
        slots.append({'name': name, 'bone': bone_name, 'attachment': name})

        px, py = pivot
        src = Image.open(SRC / (name + '.png'))
        w, h = src.size
        skins['default'][name] = {name: {
            'type': 'region', 'path': name,
            'x': round((w * 0.5 - px) * scale, 3),
            'y': round((py - h * 0.5) * scale, 3),
            'width': round(w * scale, 3),
            'height': round(h * scale, 3),
        }}

    skeleton = {
        'skeleton': {'spine': '4.2.43', 'x': 0, 'y': -850,
                     'width': 1200, 'height': 850, 'images': './', 'audio': ''},
        'bones': bones,
        'slots': slots,
        'skins': [{'name': 'default', 'attachments': skins['default']}],
        'animations': {'rest_whale_loop': {'bones': breathe()}},
    }
    (OUT / 'rest.spine-json').write_text(json.dumps(skeleton, indent=2), encoding='utf-8')

    print('page', page_size, 'regions', len(placements))
    for name, _p, _s, scale, _a in ASSEMBLY:
        x, y, w, h = region_rects[name]
        print('  %-16s atlas %4dx%-4d at (%4d,%4d)  scale %.2f' % (name, w, h, x, y, scale))


if __name__ == '__main__':
    build()
