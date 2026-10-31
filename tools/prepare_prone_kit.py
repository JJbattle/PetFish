"""Cut imagegen artwork and reproduce the static prone-reading assembly.

No painting, production rig changes, or Godot processes are involved.
"""
import json
from collections import deque
from pathlib import Path
from PIL import Image, ImageChops, ImageFilter, ImageDraw, ImageFont
from prepare_rest_kit import positioned

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/art/prone_reading_v1'
OUT = SRC / 'kit'
CANVAS = (1280, 920)


def extract():
    OUT.mkdir(exist_ok=True)
    im = Image.open(SRC / 'parts_sheet.png').convert('RGBA')
    w, h = im.size
    remaining = bytearray(im.getchannel('A').point(lambda a: 255 if a > 24 else 0).tobytes())
    groups = []
    for i in range(len(remaining)):
        if not remaining[i]:
            continue
        remaining[i] = 0
        queue, pixels = deque([i]), []
        while queue:
            k = queue.popleft()
            pixels.append(k)
            x = k % w
            for n in (k - 1 if x else -1, k + 1 if x < w - 1 else -1, k - w, k + w):
                if 0 <= n < len(remaining) and remaining[n]:
                    remaining[n] = 0
                    queue.append(n)
        if len(pixels) > 2000:
            groups.append(pixels)
    assert len(groups) == 6, len(groups)
    result = {}
    for pixels in groups:
        cx = sum(k % w for k in pixels) / len(pixels)
        cy = sum(k // w for k in pixels) / len(pixels)
        if cy < h * .62:
            name = 'head' if cx < w * .43 else ('body' if cx < w * .84 else 'arm_near')
        else:
            name = 'arm_far' if cx < w * .25 else ('pillow' if cx < w * .65 else 'book')
        assert name not in result, name
        raw = bytearray(w * h)
        for k in pixels:
            raw[k] = 255
        mask = Image.frombytes('L', im.size, bytes(raw)).filter(ImageFilter.MaxFilter(5))
        part = im.copy()
        part.putalpha(ImageChops.multiply(im.getchannel('A'), mask))
        box = part.getchannel('A').getbbox()
        crop = part.crop(box)
        padded = Image.new('RGBA', (crop.width + 24, crop.height + 24))
        padded.alpha_composite(crop, (12, 12))
        padded.putalpha(padded.getchannel('A').point(lambda a: 255 if a > 240 else a))
        padded.save(OUT / (name + '.png'))
        result[name] = {'source_bbox': list(box), 'padding': 12, 'size': list(padded.size)}
    return result


def assemble(parts):
    specs = [
        ('pillow', (660, 840), (650, 660), 1.3, 0),
        ('body', (740, 364), (540, 500), .90, 0),
        ('book', (1230, 875), (440, 750), .90, 0),
        ('arm_far', (295, 685), (380, 525), .70, -15),
        ('arm_near', (1420, 280), (600, 520), .80, 25),
        ('head', (320, 475), (515, 505), .70, 0),
    ]
    canvas = Image.new('RGBA', CANVAS)
    layers = []
    for name, pivot, position, scale, angle in specs:
        box = parts[name]['source_bbox']
        local = [pivot[0] - box[0] + 12, pivot[1] - box[1] + 12]
        tile, at = positioned(Image.open(OUT / (name + '.png')), local, position, scale, angle)
        canvas.alpha_composite(tile, at)
        layers.append(dict(name=name, pivot=local, position=list(position), scale=scale, angle=angle))
    canvas.save(OUT / 'assembled.png')
    for bg, name in [('#e6edf5', 'assembled-light.jpg'), ('#252b39', 'assembled-dark.jpg')]:
        preview = Image.new('RGBA', CANVAS, bg)
        preview.alpha_composite(canvas)
        preview.convert('RGB').save(OUT / name, quality=94)
    manifest = {'canvas': CANVAS, 'coordinates': 'top-left origin, +y down, angles clockwise; uniform scale',
                'source_size': list(Image.open(SRC / 'parts_sheet.png').size), 'parts': parts,
                'draw_order_back_to_front': layers, 'status': 'static assembly; no animation implemented'}
    (OUT / 'assembly.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    setup = {'skeleton': {'spine': '4.2.43', 'x': 0, 'y': -CANVAS[1], 'width': CANVAS[0], 'height': CANVAS[1], 'images': './'},
             'bones': [{'name': 'root'}], 'slots': [], 'skins': [{'name': 'default', 'attachments': {}}], 'animations': {}}
    for layer in layers:
        name = layer['name']
        setup['bones'].append({'name': name, 'parent': 'root', 'x': layer['position'][0],
                               'y': -layer['position'][1], 'rotation': -layer['angle']})
        setup['slots'].append({'name': name, 'bone': name, 'attachment': name})
        w, h = parts[name]['size']
        px, py = layer['pivot']
        s = layer['scale']
        setup['skins'][0]['attachments'][name] = {name: {'type': 'region', 'path': name,
            'x': (w / 2 - px) * s, 'y': -(h / 2 - py) * s, 'width': w * s, 'height': h * s}}
    (OUT / 'prone_setup.spine-json').write_text(json.dumps(setup, indent=2), encoding='utf-8')
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 18)
    sheet = Image.new('RGB', (1200, 720), '#e6edf5')
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(['head', 'body', 'arm_near', 'arm_far', 'pillow', 'book']):
        im = Image.open(OUT / (name + '.png'))
        im.thumbnail((380, 300), Image.Resampling.LANCZOS)
        x, y = i % 3 * 400, i // 3 * 360
        sheet.paste(im, (x + (400 - im.width) // 2, y + (310 - im.height) // 2), im)
        draw.text((x + 15, y + 325), name, font=font, fill='#233d61')
    sheet.save(OUT / 'parts-overview.jpg', quality=94)
    anchors = {'neck_body': [540, 500], 'head_control': [515, 505],
               'shoulder_near': [600, 520], 'elbow_near': [535, 622],
               'wrist_near': [482, 659], 'page_contact_near': [439, 657],
               'shoulder_far': [380, 525], 'elbow_far': [362, 606],
               'wrist_far': [309, 664], 'page_contact_far': [276, 727],
               'book_spine': [440, 812], 'hip_support': [820, 690]}
    (OUT / 'anchors.json').write_text(json.dumps({'coordinates': 'assembly canvas, +y down',
        'status': 'approximate anatomical guides, not an IK solution', 'points': anchors}, indent=2), encoding='utf-8')
    diagram = Image.open(OUT / 'assembled-light.jpg')
    draw = ImageDraw.Draw(diagram)
    for name, (x, y) in anchors.items():
        draw.ellipse((x-4, y-4, x+4, y+4), fill='#e84b49', outline='white')
        draw.text((x+6, y-20), name, font=font, fill='#b52027', stroke_width=2, stroke_fill='white')
    diagram.save(OUT / 'anchors.jpg', quality=94)
    print(json.dumps(parts))


if __name__ == '__main__':
    assemble(extract())
