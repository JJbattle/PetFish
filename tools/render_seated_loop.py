"""Render the `seat_work_loop` writing cycle as frame sequences + GIFs.

Produces two views of the full 4.0 s loop so the motion can be judged at both the
real desktop size and a magnified size:

- `actual`  -- the assembled content is ~1106 px tall (its alpha bbox), so it is
  mapped to the production pet's 170 px baseline with a 170/1106 factor.
- `zoom`    -- 1:1 with the authoring canvas (about 6.5x the baseline), for
  checking the 2-4 px pen stroke and breathing rise/fall.

Frames are sampled every 0.2 s across [0.0, 4.0); the 4.0 s frame is rendered
separately to confirm the loop closes seamlessly.  Output lands under
`tools/_debug/seated_loop/`.
"""
from pathlib import Path
import subprocess
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools/_debug/seated_loop'
CLIP = 'seat_work_loop'
DURATION = 4.0
STEP = 0.2
SCALES = {'actual': 170.0 / 1106.0, 'zoom': 1.0}


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
            [sys.executable, str(ROOT / 'tools/seated_preview.py'),
             '--poses', pose_list, '--scale', '%.4f' % scale,
             '--out', str(dest), '--no-diff'],
            check=True, cwd=ROOT)

    # GIFs: drop the duplicate 4.0 s frame so the loop is seamless.
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
