"""Build the prone "doodle the whale" rig.

The artist's `prepare_prone_sketch.py` already emitted a complete Spine 4.2
skeleton (`sketch_setup.json`) with the three layers as region attachments and
the `prone_sketch_loop` scribble cycle.  This script only supplies the atlas:
it pre-scales each piece to the size the region attachment declares (so atlas
`size` == region `width`/`height`, the same convention `build_seated_spine.py`
uses) and packs them onto one page.

Deliberately separate from the production `pet` rig, exactly like the seated
and prone builders: it never writes into `game/assets/pet_spine/` on its own.
`build_pose_rigs.py` is the only writer into the game asset folder.
"""
from pathlib import Path
import json

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/art/prone_sketch_v1' / 'kit'
OUT = ROOT / 'tools/_debug/prone_sketch_spine'

GUTTER = 2
ATLAS_WIDTH = 2048


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

    assembly = json.loads((SRC / 'assembly.json').read_text(encoding='utf-8'))
    scales = {row['name']: row['scale'] for row in assembly['draw_order_back_to_front']}

    # Pre-scale each piece so the atlas region matches the region attachment's
    # width/height (the setup JSON already baked scale and rotation into those).
    scaled = {}
    for name in ('whale_cushion', 'body_pad', 'drawing_arm'):
        img = Image.open(SRC / (name + '.png')).convert('RGBA')
        s = scales[name]
        if s != 1.0:
            w, h = img.size
            img = img.resize((round(w * s), round(h * s)), Image.Resampling.LANCZOS)
        scaled[name] = img

    placements, page_size = shelf_pack(list(scaled.items()))
    page = Image.new('RGBA', page_size, (0, 0, 0, 0))
    rects = {}
    for name, x, y, w, h in placements:
        page.alpha_composite(scaled[name], (x, y))
        rects[name] = (x, y, w, h)
    page.save(out_dir / 'prone_sketch.png')

    atlas = ['prone_sketch.png',
             'size: %d,%d' % page_size,
             'format: RGBA8888',
             'filter: Linear,Linear',
             'repeat: none']
    for name in scaled:
        x, y, w, h = rects[name]
        atlas += [name,
                  '  rotate: false',
                  '  xy: %d, %d' % (x, y),
                  '  size: %d, %d' % (w, h),
                  '  orig: %d, %d' % (w, h),
                  '  offset: 0, 0',
                  '  index: -1']
    (out_dir / 'prone_sketch.atlas').write_text('\n'.join(atlas) + '\n', encoding='utf-8', newline='\n')

    # The artist's skeleton is already complete (bones, slots, regions, the
    # `prone_sketch_loop` cycle); hand it through untouched.
    skeleton = json.loads((SRC / 'sketch_setup.json').read_text(encoding='utf-8'))
    (out_dir / 'prone_sketch.spine-json').write_text(
        json.dumps(skeleton, indent=2), encoding='utf-8', newline='\n')

    print('page', page_size, 'regions', len(placements))
    for name, x, y, w, h in placements:
        print('  %-14s atlas %4dx%-4d at (%4d,%4d)' % (name, w, h, x, y))


if __name__ == '__main__':
    build()
