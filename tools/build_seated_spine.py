"""Build a standalone Spine rig for the seated whale-cushion writing pose.

Reads the seven `assets/art/whale_seated_work_v1/kit/` attachments and their
static assembly manifest (`assembly.json`), packs them into one atlas, and emits
a Spine 4.2 JSON carrying a single `seat_work_loop` writing cycle.

This rig is deliberately separate from the production `pet` rig, exactly like
`build_rest_spine.py`: it never reads or writes `game/assets/pet_spine/` and is
only meant for isolated previewing until the pose is accepted and registered.

Static assembly contract
------------------------
The rig must reproduce `kit/assembled.png` exactly.  Each piece is scaled by its
manifest `scale`, rotated about its `pivot` by `-angle` (screen angles are
clockwise, Spine angles are counter-clockwise), and its pivot is placed at
`position` (canvas top-left origin, +y down).

Scale is baked into the atlas (each piece is pre-resized before packing), while
rotation stays on the bone.  Verified against the spine-godot runtime by
`build_rest_spine.py` / `tools/region_probe.py`: a region attachment's `(x, y)`
is the image **center** in the bone's local frame (+y up).  To land the piece's
pivot on the bone origin we set::

    x = (W/2 - px) * s
    y = (py - H/2) * s      (px, py = pivot in the source PNG, W/H = its size)

Skeleton is `root -> sit_body`, with `sit_head` (carrying both hair layers),
`book_lap`, `arm_far` and `arm_near_pen` as children of `sit_body`, and the
`whale_cushion` directly on `root` so it never rises with the breathing body.

Writing cycle (`seat_work_loop`, 4.0 s)
---------------------------------------
First milestone only: the arms stay single region attachments.  The writing
hand (`arm_near_pen`) scribbles by rotating a fraction of a degree about its
shoulder pivot, so the pen tip moves ~2-4 canvas px without the shoulder
drifting.  `arm_far` holds the paper with a tiny counter-rotation, and the
whole body breathes while the book and cushion stay still.  Splitting the arms
into weighted upper-arm / forearm / hand meshes for a true elbow bend and
pen-on-paper IK is the next milestone (see ASSEMBLY_GUIDE.md).
"""
from pathlib import Path
import json

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/art/whale_seated_work_v1' / 'kit'
OUT = ROOT / 'tools/_debug/seated_spine'

GUTTER = 2
ATLAS_WIDTH = 2048
CANVAS = (1280, 1280)

# name -> (pivot, position, scale, angle).  Pivot is in the padded cutout PNG,
# position is canvas coords (top-left origin, +y down), angle is clockwise.
ASSEMBLY = [
    ('whale_cushion', (-55, -608), (0, -35),   1.00, 0),
    ('hair_back',     (370, 541),  (735, 555), 0.85, 0),
    ('body_sit',      (-417, -516), (0, 0),    1.00, 0),
    ('head_front',    (370, 541),  (735, 555), 0.85, 0),
    ('book_lap',      (18, 15),    (745, 785), 0.50, 0),
    ('arm_far',       (100, 72),   (850, 620), 0.60, 10),
    ('arm_near_pen',  (91, 45),    (650, 615), 0.55, 0),
]

# Piece -> bone name (head_front and hair_back share one bone so the hair seam
# cannot drift; body_sit is renamed to sit_body like the rest rig).
def bone_of(name: str) -> str:
    if name == 'body_sit':
        return 'sit_body'
    if name in ('head_front', 'hair_back'):
        return 'sit_head'
    return name


def parent_of(name: str) -> str:
    return 'root' if name in ('whale_cushion', 'body_sit') else 'sit_body'


def write_loop() -> dict:
    """`seat_work_loop` keyframes.  Spine space: +y up, +rotation counter-clockwise.

    Rotate keys are *absolute local* rotations, so `arm_far` (setup -10 deg)
    wiggles around -10 instead of around zero.
    """
    return {
        'sit_body': {
            'translate': [
                {'time': 0.0, 'x': 0.0, 'y': 0.0},
                {'time': 1.3, 'x': 0.0, 'y': 1.4},
                {'time': 1.9, 'x': 0.0, 'y': 1.4},
                {'time': 3.7, 'x': 0.0, 'y': 0.0},
                {'time': 4.0, 'x': 0.0, 'y': 0.0},
            ],
        },
        'sit_head': {
            'rotate': [
                {'time': 0.0, 'value': 0.0},
                {'time': 1.3, 'value': 0.5},
                {'time': 1.9, 'value': 0.5},
                {'time': 3.7, 'value': -0.5},
                {'time': 4.0, 'value': 0.0},
            ],
        },
        'arm_near_pen': {
            'rotate': [
                {'time': 0.00, 'value': 0.0},
                {'time': 0.55, 'value': 0.7},
                {'time': 1.10, 'value': 0.0},
                {'time': 1.35, 'value': 0.0},
                {'time': 1.90, 'value': 0.7},
                {'time': 2.45, 'value': 0.0},
                {'time': 4.00, 'value': 0.0},
            ],
        },
        'arm_far': {
            'rotate': [
                {'time': 0.00, 'value': -10.0},
                {'time': 0.55, 'value': -10.35},
                {'time': 1.10, 'value': -10.0},
                {'time': 1.35, 'value': -10.0},
                {'time': 1.90, 'value': -10.35},
                {'time': 2.45, 'value': -10.0},
                {'time': 4.00, 'value': -10.0},
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


def build(out_dir: Path = OUT):
    out_dir.mkdir(parents=True, exist_ok=True)

    # ---- pre-scale each piece and pack --------------------------------------
    scaled = {}
    source_size = {}
    for name, pivot, _pos, scale, _angle in ASSEMBLY:
        img = Image.open(SRC / (name + '.png')).convert('RGBA')
        source_size[name] = img.size
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
    page.save(out_dir / 'seated.png')

    # ---- atlas --------------------------------------------------------------
    atlas = ['seated.png',
             'size: %d,%d' % page_size,
             'format: RGBA8888',
             'filter: Linear,Linear',
             'repeat: none']
    for name, *_ in ASSEMBLY:
        x, y, w, h = region_rects[name]
        atlas += [name,
                  '  rotate: false',
                  '  xy: %d, %d' % (x, y),
                  '  size: %d, %d' % (w, h),
                  '  orig: %d, %d' % (w, h),
                  '  offset: 0, 0',
                  '  index: -1']
    (out_dir / 'seated.atlas').write_text('\n'.join(atlas) + '\n', encoding='utf-8', newline='\n')

    # ---- skeleton -----------------------------------------------------------
    # Parents must precede their children in the bone array.
    by_name = {row[0]: row for row in ASSEMBLY}
    bones = [{'name': 'root'}]
    for name in ('body_sit', 'whale_cushion', 'hair_back', 'book_lap', 'arm_far', 'arm_near_pen'):
        _pivot, position, _scale, angle = by_name[name][1:]
        bones.append({'name': bone_of(name), 'parent': parent_of(name),
                      'x': round(position[0], 3), 'y': round(-position[1], 3),
                      'rotation': round(-angle, 3)})

    slots = []
    skins = {'default': {}}
    for name, pivot, position, scale, angle in ASSEMBLY:
        bone_name = bone_of(name)
        slots.append({'name': name, 'bone': bone_name, 'attachment': name})

        px, py = pivot
        w, h = source_size[name]
        skins['default'][name] = {name: {
            'type': 'region', 'path': name,
            'x': round((w * 0.5 - px) * scale, 3),
            'y': round((py - h * 0.5) * scale, 3),
            'width': round(w * scale, 3),
            'height': round(h * scale, 3),
        }}

    skeleton = {
        'skeleton': {'spine': '4.2.43', 'x': 0, 'y': -CANVAS[1],
                     'width': CANVAS[0], 'height': CANVAS[1], 'images': './', 'audio': ''},
        'bones': bones,
        'slots': slots,
        'skins': [{'name': 'default', 'attachments': skins['default']}],
        'animations': {'seat_work_loop': {'bones': write_loop()}},
    }
    (out_dir / 'seated.spine-json').write_text(json.dumps(skeleton, indent=2), encoding='utf-8')

    print('page', page_size, 'regions', len(placements))
    for name, _p, _pos, scale, _a in ASSEMBLY:
        x, y, w, h = region_rects[name]
        print('  %-14s atlas %4dx%-4d at (%4d,%4d)  scale %.2f' % (name, w, h, x, y, scale))


if __name__ == '__main__':
    build()
