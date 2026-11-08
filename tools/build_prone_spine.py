"""Build the v3 prone-reading rig with swappable eyes and mouth.

Packs the v3 fluke, feet, reading base and four expression textures.
The face_setup.json from prepare_prone_expressions.py preserves the reading
mesh and registers the new eye and mouth slots. Add the prone_read_loop cycle.

Deliberately separate from the production `pet` rig, exactly like
`build_seated_spine.py` / `build_rest_spine.py`: it never writes into
`game/assets/pet_spine/` on its own and is only meant for isolated previewing;
`build_pose_rigs.py` is the only writer into the game asset folder.

The v3 master folds the legs towards the head. The fluke and feet use the
new master's landmarks. Book, pillow, fingers and sleeves share the reading
mesh so their contact points stay registered.

Reading cycle (`prone_read_loop`, 4.0 s)
----------------------------------------
Follows ASSEMBLY_GUIDE.md step 4: `reading` leans ~0.6 deg toward the book,
holds half a second, and eases back; the `fluke` sways ~1 deg half a beat
late; one foot (`shoe_near`) gives an intermittent ~1 deg nudge.  Every curve
closes at 0 so the loop is seamless.
"""
from pathlib import Path
import json

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/art/prone_reading_v3' / 'kit'
FACE = SRC.parent / 'expressions'
OUT = ROOT / 'tools/_debug/prone_spine'

GUTTER = 2
ATLAS_WIDTH = 2048

PIECE_DIRS = {name: SRC for name in ('fluke', 'shoe_far', 'shoe_near', 'whale_cushion')}
PIECE_DIRS.update({name: FACE for name in ('reading_base', 'eyes_neutral',
                  'eyes_happy', 'mouth_neutral', 'mouth_happy')})


def read_loop() -> dict:
    """`prone_read_loop` keyframes.  Spine space: +y up, +rotation counter-clockwise.

    `reading`/`fluke`/`shoe_near` have zero setup rotation, so the keys are
    absolute from zero.  All tracks return to 0 at 4.0 s to close the loop.
    """
    return {
        'reading': {
            'rotate': [
                {'time': 0.0, 'value': 0.0},
                {'time': 1.5, 'value': 0.6},
                {'time': 2.0, 'value': 0.6},
                {'time': 4.0, 'value': 0.0},
            ],
        },
        'fluke': {
            'rotate': [
                {'time': 0.0, 'value': 0.0},
                {'time': 2.0, 'value': 1.0},
                {'time': 2.5, 'value': 1.0},
                {'time': 4.0, 'value': 0.0},
            ],
        },
        'shoe_near': {
            'rotate': [
                {'time': 0.0, 'value': 0.0},
                {'time': 2.6, 'value': 0.0},
                {'time': 3.0, 'value': 1.0},
                {'time': 3.4, 'value': 0.0},
                {'time': 4.0, 'value': 0.0},
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

    imgs = {name: Image.open(folder / (name + '.png')).convert('RGBA')
            for name, folder in PIECE_DIRS.items()}
    placements, page_size = shelf_pack(list(imgs.items()))
    page = Image.new('RGBA', page_size, (0, 0, 0, 0))
    rects = {}
    for name, x, y, w, h in placements:
        page.alpha_composite(imgs[name], (x, y))
        rects[name] = (x, y, w, h)
    page.save(out_dir / 'prone.png')

    atlas = ['prone.png',
             'size: %d,%d' % page_size,
             'format: RGBA8888',
             'filter: Linear,Linear',
             'repeat: none']
    for name in imgs:
        x, y, w, h = rects[name]
        atlas += [name,
                  '  rotate: false',
                  '  xy: %d, %d' % (x, y),
                  '  size: %d, %d' % (w, h),
                  '  orig: %d, %d' % (w, h),
                  '  offset: 0, 0',
                  '  index: -1']
    (out_dir / 'prone.atlas').write_text('\n'.join(atlas) + '\n', encoding='utf-8', newline='\n')

    # ---- skeleton: reuse the weight-painted mesh from the kit --------------
    skeleton = json.loads((FACE / 'face_setup.json').read_text(encoding='utf-8'))
    skeleton['animations'] = {'prone_read_loop': {'bones': read_loop()}}
    (out_dir / 'prone.spine-json').write_text(
        json.dumps(skeleton, indent=2), encoding='utf-8', newline='\n')

    print('page', page_size, 'regions', len(placements))
    for name, x, y, w, h in placements:
        print('  %-9s atlas %4dx%-4d at (%4d,%4d)' % (name, w, h, x, y))


if __name__ == '__main__':
    build()
