"""Render the `rest_whale_loop` breathing cycle as frame sequences + GIFs.

Produces two views of the full 4.8 s loop so the motion can be judged at both the
real desktop size and a magnified size:

- `actual`  -- 170 px baseline, matching the production pet's on-screen scale
  (production maps its 820 px-tall content to PET_TARGET_H = 170 px, so the same
  170/820 factor is applied to the rest canvas to keep the character the same
  physical density).
- `zoom`    -- 1:1 with the authoring canvas (about 4.8x the baseline), for
  checking the 2-3 px breathing rise/fall and head sway.

Frames are sampled every 0.2 s across [0.0, 4.8); the 4.8 s frame is rendered
separately to confirm the loop closes seamlessly.  Output lands under
`tools/_debug/rest_loop/`.
"""
from pathlib import Path
import subprocess
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools/_debug/rest_loop'
CLIP = 'rest_whale_loop'
DURATION = 4.8
STEP = 0.2
SCALES = {'actual': 170.0 / 820.0, 'zoom': 1.0}


def frames():
    t = 0.0
    while t < DURATION - 1e-6:
        yield t
        t += STEP
    yield DURATION  # loop-closure check


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    pose_list = ','.join('%s:%.1f' % (CLIP, t) for t in frames())
    for name, scale in SCALES.items():
        dest = OUT / name
        dest.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [sys.executable, str(ROOT / 'tools/rest_preview.py'),
             '--poses', pose_list, '--scale', '%.4f' % scale,
             '--out', str(dest), '--no-diff'],
            check=True, cwd=ROOT)

    # GIFs: drop the duplicate 4.8 s frame so the loop is seamless.
    for name in SCALES:
        imgs = []
        t = 0.0
        while t < DURATION - 1e-6:
            imgs.append(Image.open(OUT / name / ('%s_%.3f.png' % (CLIP, t))).convert('RGBA'))
            t += STEP
        imgs[0].save(OUT / ('%s.gif' % name), save_all=True,
                     append_images=imgs[1:], duration=200, loop=0,
                     disposal=2, transparency=0)
    print('loop previews ->', OUT)


if __name__ == '__main__':
    main()
