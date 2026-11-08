"""Render activity clips as frame sequences + GIFs for review.

Mirrors tools/render_seated_loop.py: each clip is sampled at a fixed step across
[0, duration) plus the duration frame (loop-closure check), rendered through
tools/activity_preview.py, and assembled into a GIF.  Two scales are produced:
`zoom` (1:1 authoring canvas) for judging articulation, and `actual` (the fish
roughly at the desktop size) for judging real-size legibility.
"""
from pathlib import Path
import subprocess
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'tools/_debug/activity_loop'

# clip -> (duration, step)
CLIPS = {
    'activity_neutral': (2.0, 0.1),
    'activity_ready': (10.0, 0.2),
    'activity_march_cycle': (2.0, 0.1),
    'activity_heel_cycle': (4.0, 0.15),
    'activity_relax': (5.0, 0.2),
}

# Whole character is ~853 px tall in the 1024 canvas; ~0.2 puts it near 170 px.
SCALES = {'zoom': 1.0, 'actual': 0.2}


def frames(duration, step):
    t = 0.0
    while t < duration - 1e-6:
        yield t
        t += step
    yield duration  # loop-closure check


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for clip, (duration, step) in CLIPS.items():
        pose_list = ','.join('%s:%.3f' % (clip, t) for t in frames(duration, step))
        for name, scale in SCALES.items():
            dest = OUT / name / clip
            dest.mkdir(parents=True, exist_ok=True)
            subprocess.run(
                [sys.executable, str(ROOT / 'tools/activity_preview.py'),
                 '--rig', 'activity_standing',
                 '--poses', pose_list, '--scale', '%.4f' % scale,
                 '--out', str(dest), '--no-diff'],
                check=True, cwd=ROOT)
            imgs = []
            t = 0.0
            while t < duration - 1e-6:
                imgs.append(Image.open(dest / ('%s_%.3f.png' % (clip, t))).convert('RGBA'))
                t += step
            if imgs:
                imgs[0].save(dest.parent / ('%s.gif' % clip), save_all=True,
                             append_images=imgs[1:], duration=int(step * 1000), loop=0,
                             disposal=2, transparency=0)
    print('activity clip previews ->', OUT)


if __name__ == '__main__':
    main()
