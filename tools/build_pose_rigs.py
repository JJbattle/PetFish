"""Build the seated + prone rigs into the production asset folder.

The seated (`whale_seated_work_v1`) and prone (`prone_reading_v2`) poses are
separate Spine skeletons from the standing `pet` rig, so they are emitted as
their own `.spine-json` / `.atlas` / `.png` triplets next to `pet.*` and loaded
by `pet.gd` as additional SpineSprite nodes that swap in for the `working` and
`slack` states.

This also writes a per-rig alpha silhouette.  The seated/prone animations move
only a couple of canvas pixels (a ~1 deg head nod and a sub-degree arm scribble),
so the setup-pose alpha dilated by the same 21 px MaxFilter the standing rig
uses already covers the whole loop without a Godot render pass.
"""
from pathlib import Path
import sys

from PIL import Image, ImageFilter

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_seated_spine
import build_prone_spine

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'game/assets/pet_spine'

SILHOUETTES = [
    ('assets/art/whale_seated_work_v1/kit/assembled.png', 'seated_silhouette.png', (1280, 1280)),
    ('assets/art/prone_reading_v2/kit/assembled.png', 'prone_silhouette.png', (1536, 1024)),
]


def write_silhouette(src_rel: str, out_name: str, canvas: tuple) -> None:
    src = Image.open(ROOT / src_rel).convert('RGBA')
    alpha = src.getchannel('A').point(lambda v: 255 if v > 25 else 0)
    alpha = alpha.filter(ImageFilter.MaxFilter(21))
    out = Image.new('RGBA', canvas, 'white')
    out.putalpha(alpha)
    out.save(DEST / out_name)
    print('silhouette', out_name, 'canvas', canvas, 'bbox', alpha.getbbox())


def main() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    build_seated_spine.build(DEST)
    build_prone_spine.build(DEST)
    for src_rel, out_name, canvas in SILHOUETTES:
        write_silhouette(src_rel, out_name, canvas)
    print('pose rigs ->', DEST)


if __name__ == '__main__':
    main()
