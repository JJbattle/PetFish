"""Assemble the 2026-11-07 knee/loop/heel review evidence from the isolated
activity rig renders (see render via activity_preview.py).  Read-only with
respect to the source rig, builder and original captures.

Produces, under docs/activity-review-20261106/:
  * knee-march-evidence.jpg   -- enlarged knee crops (neutral / left peak / right
                                 peak / settle) for both legs on one background
  * knee-march-actual.jpg     -- full-body actual-size frames
  * march-loop-zoom.gif       -- continuous 6 s (2 s x 3) leg-region loop
  * march-loop-actual.gif     -- continuous 6 s loop at desktop size
  * heel-regression-evidence.jpg -- sock/ankle crops at the swap instants
  * knee-analysis-evidence.json -- numeric edge traces (concave/convex sides)
"""
from pathlib import Path
import json

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'tools/_debug/activity_knee_r2'
DOC = ROOT / 'docs/activity-review-20261106'
BG = (231, 237, 243)          # uniform light blue-grey (same background everywhere)
FONT = 'C:/Windows/Fonts/msyh.ttc'


def _font(sz):
    try:
        return ImageFont.truetype(FONT, sz)
    except Exception:
        return ImageFont.load_default()


def load(path, scale=1.0):
    img = Image.open(path).convert('RGBA')
    if scale != 1.0:
        img = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.Resampling.NEAREST)
    return img


def on_bg(img, bg=BG):
    """Composite an RGBA frame onto a solid background."""
    tile = Image.new('RGBA', img.size, bg + (255,))
    tile.alpha_composite(img)
    return tile.convert('RGB')


def crop_on_bg(img, box, up=1):
    c = img.crop(box)
    if up != 1:
        c = c.resize((c.width * up, c.height * up), Image.Resampling.NEAREST)
    return on_bg(c)


# Leg scan boxes (screen pixels at scale 1.0).  Left leg occupies x438..520,
# right leg x522..604; both span roughly y730..830 (skirt hem ~745, knee ~764).
LEFT = (438, 730, 520, 830)
RIGHT = (522, 730, 604, 830)


def knee_composite():
    frames = {
        'neutral 0.0': 'activity_march_cycle_0.000.png',
        'L peak 0.5': 'activity_march_cycle_0.500.png',
        'settle 1.0': 'activity_march_cycle_1.000.png',
        'R peak 1.5': 'activity_march_cycle_1.500.png',
        'neutral 2.0': 'activity_march_cycle_2.000.png',
    }
    # two rows: left leg (x438..520) and right leg (x522..604); columns: neutral,
    # left peak, right peak, settle.
    cols = ['neutral 0.0', 'L peak 0.5', 'R peak 1.5', 'settle 1.0']
    rows = [('L leg', LEFT), ('R leg', RIGHT)]
    up = 3
    cw, ch = (LEFT[2] - LEFT[0]) * up, (LEFT[3] - LEFT[1]) * up
    pad, lab = 10, 24
    W = pad + len(cols) * (cw + pad)
    H = lab + len(rows) * (ch + lab + pad)
    panel = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(panel)
    f = _font(18)
    for ci, cname in enumerate(cols):
        d.text((pad + ci * (cw + pad) + 6, 4), cname, font=f, fill=(35, 61, 97))
    for ri, (rname, box) in enumerate(rows):
        for ci, cname in enumerate(cols):
            img = load(SRC / 'knee_zoom' / frames[cname])
            tile = crop_on_bg(img, box, up)
            x = pad + ci * (cw + pad)
            y = lab + ri * (ch + lab + pad)
            panel.paste(tile, (x, y))
            if ci == 0:
                d.text((x + 6, y + 6), rname, font=f, fill=(35, 61, 97))
    out = DOC / 'knee-march-evidence.jpg'
    panel.save(out, quality=94)
    return out


def actual_composite():
    names = [('0.0 neutral', 'activity_march_cycle_0.000.png'),
             ('0.5 L peak', 'activity_march_cycle_0.500.png'),
             ('1.0 settle', 'activity_march_cycle_1.000.png'),
             ('1.5 R peak', 'activity_march_cycle_1.500.png')]
    imgs = []
    for label, fn in names:
        img = load(SRC / 'knee_actual' / fn)
        imgs.append((label, img))
    # actual frames are 205x205; lay them out 4 across
    w = h = imgs[0][1].width
    pad, lab = 8, 22
    W = pad + len(imgs) * (w + pad)
    H = lab + h + pad
    panel = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(panel)
    f = _font(16)
    for i, (label, img) in enumerate(imgs):
        x = pad + i * (w + pad)
        panel.paste(on_bg(img), (x, lab))
        d.text((x + 4, 2), label, font=f, fill=(35, 61, 97))
    out = DOC / 'knee-march-actual.jpg'
    panel.save(out, quality=94)
    return out


def loop_gif(scale_name, src_sub, box, up=1, label=''):
    """Assemble the continuous 6 s loop frames into a GIF on a uniform background.

    One shared 256-colour palette is built from all frames so the encoder keeps
    every frame (no per-frame palette / disposal merging) and the loop stays
    flicker-free on the uniform background.
    """
    paths = sorted((SRC / src_sub).glob('activity_march_cycle_*.png'),
                   key=lambda p: float(p.stem.rsplit('_', 1)[1]))
    # 15 fps, duration 6.0 -> 91 frames (0..6.0 inclusive)
    frames = []
    for p in paths:
        img = load(p)
        if box:
            img = img.crop(box)
        if up != 1:
            img = img.resize((img.width * up, img.height * up), Image.Resampling.NEAREST)
        frames.append(on_bg(img))

    cols, thumb = 8, 96
    rows = (len(frames) + cols - 1) // cols
    training = Image.new('RGB', (cols * thumb, rows * thumb))
    for i, f in enumerate(frames):
        t = f.copy()
        t.thumbnail((thumb, thumb))
        training.paste(t, ((i % cols) * thumb, (i // cols) * thumb))
    pal = training.quantize(colors=255, method=Image.Quantize.MEDIANCUT)

    indexed = [f.quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    out = DOC / ('march-loop-%s.gif' % scale_name)
    indexed[0].save(out, save_all=True, append_images=indexed[1:],
                    duration=int(1000 / 15), loop=0, disposal=2, optimize=False)
    return out, len(indexed)


def heel_composite():
    instants = ['activity_heel_cycle_0.990.png', 'activity_heel_cycle_1.000.png',
                'activity_heel_cycle_1.010.png', 'activity_heel_cycle_3.490.png',
                'activity_heel_cycle_3.500.png', 'activity_heel_cycle_3.510.png']
    labels = ['0.99', '1.00', '1.01', '3.49', '3.50', '3.51']
    # ankle/sock region: left leg x438..520 and right leg x522..604, y780..912
    box = (438, 780, 604, 912)
    up = 2
    cw, ch = (box[2] - box[0]) * up, (box[3] - box[1]) * up
    pad, lab = 8, 22
    W = pad + len(instants) * (cw + pad)
    H = lab + ch + pad
    panel = Image.new('RGB', (W, H), BG)
    d = ImageDraw.Draw(panel)
    f = _font(16)
    for i, (fn, lb) in enumerate(zip(instants, labels)):
        img = load(SRC / 'heel_zoom' / fn)
        tile = crop_on_bg(img, box, up)
        x = pad + i * (cw + pad)
        panel.paste(tile, (x, lab))
        d.text((x + 4, 2), lb + ' s', font=f, fill=(35, 61, 97))
    out = DOC / 'heel-regression-evidence.jpg'
    panel.save(out, quality=94)
    return out


def numeric_analysis():
    """1 px edge traces of the concave (lateral) and convex (medial) sides of the
    left leg at neutral vs the left peak, plus the heel sock width step."""
    def edges(fn, xmin, xmax, ymin, ymax, thresh=128):
        a = load(SRC / 'knee_zoom' / fn).getchannel('A')
        out = []
        for y in range(ymin, ymax):
            xs = [x for x in range(xmin, xmax) if a.getpixel((x, y)) > thresh]
            if xs:
                out.append([y, min(xs), max(xs)])
        return out

    # left leg, below the skirt hem (~y746), scan x438..520
    neutral = edges('activity_march_cycle_0.000.png', 438, 520, 746, 820)
    peak = edges('activity_march_cycle_0.500.png', 438, 520, 746, 820)

    def profile(rows):
        return [{'y': r[0], 'outer': r[1], 'inner': r[2], 'w': r[2] - r[1] + 1} for r in rows]

    # concave (outer) edge pinch: max outer-x at the knee minus the outer-x of the
    # thigh just below the skirt and of the calf below the knee.
    pn, pp = profile(neutral), profile(peak)
    def outer_minmax(p):
        ys = [r['y'] for r in p]
        ox = [r['outer'] for r in p]
        return ys, ox

    p_ys, p_ox = outer_minmax(pp)
    knee_i = max(range(len(p_ox)), key=lambda i: p_ox[i])   # peak = most inward
    thigh_i = min(range(len(p_ys)), key=lambda i: abs(p_ys[i] - 752))
    calf_i = min(range(len(p_ys)), key=lambda i: abs(p_ys[i] - 800))
    pinch_thigh = p_ox[knee_i] - p_ox[thigh_i]
    pinch_calf = p_ox[knee_i] - p_ox[calf_i]

    # heel sock width step at the swap instants
    def sock_width(fn):
        a = load(SRC / 'heel_zoom' / fn).getchannel('A')
        # right leg ankle centerline width just above the shoe (y ~800..840)
        widths = []
        for y in range(800, 850):
            xs = [x for x in range(522, 604) if a.getpixel((x, y)) > 128]
            if xs:
                widths.append(max(xs) - min(xs) + 1)
        return round(sum(widths) / len(widths), 1) if widths else None

    heel = {t: sock_width('activity_heel_cycle_%.3f.png' % t)
            for t in (0.99, 1.0, 1.01, 3.49, 3.5, 3.51)}

    return {
        'left_knee': {
            'neutral_outer_752': p_ox[thigh_i] if thigh_i < len(p_ox) else None,
            'peak_outer_knee_y': p_ys[knee_i],
            'peak_outer_knee_x': p_ox[knee_i],
            'peak_outer_calf800_x': p_ox[calf_i],
            'concave_pinch_vs_thigh_px': pinch_thigh,
            'concave_pinch_vs_calf_px': pinch_calf,
            'profile_peak': pp[knee_i],
            'neutral_profile': pn,
            'peak_profile': pp,
        },
        'heel_sock_avg_width_px': heel,
    }


def main():
    DOC.mkdir(parents=True, exist_ok=True)
    a = knee_composite()
    b = actual_composite()
    c, nz = loop_gif('zoom', 'loop_zoom', (438, 720, 604, 915), up=2)
    d, na = loop_gif('actual', 'loop_actual', None, up=1)
    e = heel_composite()
    ev = numeric_analysis()
    (DOC / 'knee-analysis-evidence.json').write_text(json.dumps(ev, indent=2), encoding='utf-8')
    print('knee composite     ->', a)
    print('actual composite   ->', b)
    print('loop zoom gif      ->', c, '(%d frames)' % nz)
    print('loop actual gif    ->', d, '(%d frames)' % na)
    print('heel composite     ->', e)
    print('analysis           ->', DOC / 'knee-analysis-evidence.json')
    print(json.dumps({k: v for k, v in ev.items() if k != 'left_knee'},
                     indent=2, ensure_ascii=False))


if __name__ == '__main__':
    main()
