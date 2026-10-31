"""Export the generated rest atlas as individual RGBA rig attachments.

This performs transparent component extraction and assembly, never repainting
the artwork. It does not change the production atlas or animations.
"""
from collections import deque
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageChops

from deepseek_whale import render_whale

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/art/rest_whale_v1'


def extract():
    source = Image.open(OUT / 'parts_sheet.png').convert('RGBA')
    w, h = source.size
    mask = bytearray(source.getchannel('A').point(lambda a: 255 if a > 24 else 0).tobytes())
    groups = []
    for index in range(len(mask)):
        if not mask[index]:
            continue
        mask[index] = 0
        queue, pixels = deque([index]), []
        while queue:
            pixel = queue.popleft()
            pixels.append(pixel)
            x, y = pixel % w, pixel // w
            for neighbour in (pixel - 1 if x else -1, pixel + 1 if x < w - 1 else -1,
                              pixel - w, pixel + w):
                if 0 <= neighbour < len(mask) and mask[neighbour]:
                    mask[neighbour] = 0
                    queue.append(neighbour)
        if len(pixels) > 500:
            groups.append(pixels)
    if len(groups) != 6:
        raise ValueError(f'Expected six independent attachments, found {len(groups)}')
    names = ['head_sleep', 'arm_near', 'body_legs_tail', 'head_drowsy_reference', 'arm_far', 'pillow']
    result = {}
    for name, pixels in zip(names, groups):
        data = bytearray(w * h)
        for pixel in pixels:
            data[pixel] = 255
        selected = Image.frombytes('L', (w, h), bytes(data)).filter(ImageFilter.MaxFilter(5))
        piece = source.copy()
        piece.putalpha(ImageChops.multiply(source.getchannel('A'), selected))
        box = piece.getbbox()
        crop = piece.crop(box)
        padded = Image.new('RGBA', (crop.width + 24, crop.height + 24))
        padded.alpha_composite(crop, (12, 12))
        padded.save(OUT / (name + '.png'))
        result[name] = {'source_bbox': list(box), 'padding': 12, 'size': list(padded.size)}
    render_whale(300, (65, 112, 242, 255)).save(OUT / 'whale.png')
    result['whale'] = {'source': 'tools/deepseek_whale.py', 'size': [300, 221]}
    return result


def positioned(image, pivot, target, scale=1, angle=0):
    """Screen coordinates, positive angles clockwise; uniform scale only."""
    image = image.resize((round(image.width * scale), round(image.height * scale)), Image.Resampling.LANCZOS)
    px, py = pivot[0] * scale, pivot[1] * scale
    # Pad around pivot before rotating, keeping attachment positioning exact.
    extent = int(max(px, py, image.width-px, image.height-py) * 2 + 8)
    tile = Image.new('RGBA', (extent * 2, extent * 2))
    tile.alpha_composite(image, (round(extent-px), round(extent-py)))
    tile = tile.rotate(-angle, Image.Resampling.BICUBIC)
    return tile, (round(target[0]-extent), round(target[1]-extent))


def assemble(parts):
    layers = [
        {'name': 'pillow', 'pivot': [12, 12], 'position': [160, 390], 'scale': 1.1, 'angle': 0},
        {'name': 'body_legs_tail', 'pivot': [12, 12], 'position': [480, 380], 'scale': .9, 'angle': 0},
        {'name': 'head_sleep', 'pivot': [322, 391], 'position': [536, 466], 'scale': 1, 'angle': 0},
        {'name': 'arm_far', 'pivot': [257, 57], 'position': [604, 520], 'scale': .62, 'angle': -10},
        {'name': 'whale', 'pivot': [0, 0], 'position': [420, 550], 'scale': .64, 'angle': 0},
        {'name': 'arm_near', 'pivot': [239, 70], 'position': [606, 475], 'scale': .65, 'angle': 20},
    ]
    canvas = Image.new('RGBA', (1200, 850))
    for layer in layers:
        image = Image.open(OUT / (layer['name'] + '.png')).convert('RGBA')
        tile, at = positioned(image, layer['pivot'], layer['position'], layer['scale'], layer['angle'])
        canvas.alpha_composite(tile, at)
    canvas.save(OUT / 'assembled.png')
    preview = Image.new('RGBA', canvas.size, '#e6edf5')
    preview.alpha_composite(canvas)
    preview.convert('RGB').save(OUT / 'assembled-check.jpg', quality=94)
    manifest = {'version': 1, 'canvas': [1200, 850],
                'coordinates': 'pixels; origin top-left; +y down; angle degrees clockwise',
                'status': 'static assembly guide; not a production Spine export',
                'parts': parts, 'draw_order_back_to_front': layers}
    (OUT / 'assembly.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    # Optional Spine editor Data Import seed. This is a setup pose, not an
    # animated/exported production rig. Root origin is canvas top-left.
    skeleton = {'skeleton': {'spine': '4.2.43', 'x': 0, 'y': -850,
                             'width': 1200, 'height': 850, 'images': './'},
                'bones': [{'name': 'root'}], 'slots': [],
                'skins': [{'name': 'default', 'attachments': {}}], 'animations': {}}
    body = next(layer for layer in layers if layer['name'] == 'body_legs_tail')
    # Bone definitions must precede their children; slot order stays visual.
    ordered = [body] + [layer for layer in layers if layer is not body]
    for layer in ordered:
        name = layer['name']
        parent = 'root' if name in ('pillow', 'body_legs_tail') else 'rest_body'
        bone_name = 'rest_body' if name == 'body_legs_tail' else name
        bx, by = layer['position']
        if parent == 'rest_body':
            bx -= body['position'][0]
            by -= body['position'][1]
        skeleton['bones'].append({'name': bone_name, 'parent': parent,
                                  'x': bx, 'y': -by, 'rotation': -layer['angle']})
    for layer in layers:
        name = layer['name']
        bone = 'rest_body' if name == 'body_legs_tail' else name
        skeleton['slots'].append({'name': name, 'bone': bone, 'attachment': name})
        with Image.open(OUT / (name + '.png')) as part:
            width, height = part.size
        scale = layer['scale']
        skeleton['skins'][0]['attachments'][name] = {name: {
            'type': 'region', 'path': name,
            'x': (width / 2-layer['pivot'][0])*scale,
            'y': -(height / 2-layer['pivot'][1])*scale,
            'width': width*scale, 'height': height*scale}}
    (OUT / 'rest_setup.spine-json').write_text(json.dumps(skeleton, indent=2), encoding='utf-8')
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
    sheet = Image.new('RGB', (1200, 720), '#e6edf5')
    draw = ImageDraw.Draw(sheet)
    labels = [('head_sleep', '闭眼头部与头发'), ('body_legs_tail', '无头无臂身体'),
              ('arm_near', '近侧整条袖子与手'), ('arm_far', '远侧整条袖子与手'),
              ('pillow', '补全表面的枕头'), ('whale', '仓库原生鲸鱼图标')]
    for i, (name, title) in enumerate(labels):
        image = Image.open(OUT / (name + '.png')).convert('RGBA')
        image.thumbnail((380, 300), Image.Resampling.LANCZOS)
        x, y = (i % 3) * 400, (i // 3) * 360
        sheet.paste(image, (x + (400-image.width)//2, y + (310-image.height)//2), image)
        draw.text((x+18, y+320), title, font=font, fill='#233d61')
    sheet.save(OUT / 'parts-overview.jpg', quality=94)
    print('Exported six attachment PNGs + one unused expression reference; setup JSON, assembly and previews')


if __name__ == '__main__':
    assemble(extract())
