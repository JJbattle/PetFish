"""Prepare the slack expression handoff without changing the production rig."""
import copy
import json
import math
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image, ImageChops, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'assets/art/prone_reading_v3'
OUT = ART / 'expressions'
KIT = ART / 'kit'
SOURCE_BOX = (305, 510, 685, 669)
# Include lashes crossing the bang edge. Retain v3 skin and hair around edits.
FEATURES = {'eyes': [(317, 551, 459, 638), (522, 519, 671, 613)],
            'mouth': [(481, 638, 519, 660)]}


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def split_opacity(image):
    """Share original coverage across a narrow sampling gutter.

    Transmittances multiply under alpha compositing. Split them exponentially
    so both textures can be linearly filtered without a rectangular seam.
    """
    top = Image.new('L', image.size)
    bottom = Image.new('L', image.size)
    a = image.getchannel('A').load()
    for y in range(image.height):
        for x in range(image.width):
            t = min(x, y, image.width-1-x, image.height-1-y, 8) / 8
            opacity = a[x,y]
            if t == 0:
                bottom.putpixel((x,y), opacity)
            elif t == 1:
                top.putpixel((x,y), opacity)
            else:
                front = round(255*(1-(1-opacity/255)**t))
                back = round(255*(opacity-front)/(255-front)) if front < 255 else opacity
                top.putpixel((x,y), front)
                bottom.putpixel((x,y), back)
    return top, bottom


def patch_mesh(source, offset, bounds):
    """Reuse source triangles, vertex weights and bind coordinates for each tile."""
    width, height = source['width'], source['height']
    uv = list(zip(source['uvs'][::2], source['uvs'][1::2]))
    xy = [(offset[0] + u*width, offset[1] + v*height) for u,v in uv]
    weighted = []
    data = source['vertices']
    cursor = 0
    while cursor < len(data):
        end = cursor + 1 + 4 * data[cursor]
        weighted.append(data[cursor:end])
        cursor = end
    left, top, right, bottom = bounds
    triangles = []
    for pos in range(0, len(source['triangles']), 3):
        tri = source['triangles'][pos:pos+3]
        xs, ys = zip(*(xy[k] for k in tri))
        if max(xs) >= left and min(xs) <= right and max(ys) >= top and min(ys) <= bottom:
            triangles.extend(tri)
    used = set(triangles)
    xs, ys = zip(*(xy[k] for k in used))
    box = (math.floor(min(xs))-2, math.floor(min(ys))-2,
           math.ceil(max(xs))+2, math.ceil(max(ys))+2)
    # Store perimeter first, clockwise in image space, then the inner points.
    ix = sorted(used, key=lambda k: (xy[k][1], xy[k][0]))
    upper = [k for k in ix if xy[k][1] == min(ys)]
    lower = [k for k in ix if xy[k][1] == max(ys)]
    mid = [k for k in ix if k not in upper and k not in lower]
    perimeter = upper + [k for k in mid if xy[k][0] == max(xs)] + lower[::-1] + [k for k in reversed(mid) if xy[k][0] == min(xs)]
    ordered = perimeter + [k for k in mid if k not in perimeter]
    index = {k:i for i,k in enumerate(ordered)}
    w,h = box[2]-box[0], box[3]-box[1]
    mesh = dict(type='mesh', width=w, height=h, hull=len(perimeter),
                triangles=[index[k] for k in triangles],
                vertices=[v for k in ordered for v in weighted[k]],
                uvs=[v for k in ordered for v in ((xy[k][0]-box[0])/w,(xy[k][1]-box[1])/h)])
    return box, mesh


def main():
    neutral = Image.open(ART/'character_without_cushion.png').convert('RGBA')
    generated = Image.open(OUT/'happy_source.png').convert('RGBA')
    base = Image.open(KIT/'reading.png').convert('RGBA')
    registration = json.loads((KIT/'assembly.json').read_text())
    offset = registration['reading']['top_left']
    skeleton = json.loads((KIT/'prone_v3.json').read_text())
    skin = skeleton['skins'][0]['attachments']
    original_mesh = skin['reading']['reading']
    skin['reading']['reading']['path'] = 'reading_base'
    happy = neutral.copy()
    positions = {}
    rebuilt = Image.new('RGBA',neutral.size)
    for feature, boxes in FEATURES.items():
        bounds = (min(b[0] for b in boxes),min(b[1] for b in boxes),
                  max(b[2] for b in boxes),max(b[3] for b in boxes))
        box, mesh = patch_mesh(original_mesh, offset, bounds)
        slot = 'prone_'+feature
        skeleton['slots'].append(dict(name=slot,bone='root',attachment='neutral'))
        skin[slot] = {}
        positions[slot] = {'tile_top_left':box[:2], 'pixel_rectangles':boxes}
        for state in ('neutral','happy'):
            tile = Image.new('RGBA',(mesh['width'],mesh['height']))
            for x,y,r,b in boxes:
                original = neutral.crop((x,y,r,b))
                front, back = split_opacity(original)
                underlay = original.copy()
                underlay.putalpha(back)
                base.paste(underlay,(x-offset[0],y-offset[1]))
                if state == 'happy':
                    feature_im = generated.crop((x-SOURCE_BOX[0],y-SOURCE_BOX[1],r-SOURCE_BOX[0],b-SOURCE_BOX[1]))
                    # Keep original opacity and a 3 px transition into unchanged art.
                    feature_im.putalpha(original.getchannel('A'))
                    mask = Image.new('L',original.size)
                    pen = ImageDraw.Draw(mask)
                    for n,opacity in enumerate((0,85,170,255)):
                        pen.rectangle((n,n,r-x-1-n,b-y-1-n),fill=opacity)
                    original = Image.composite(feature_im,original,mask)
                    happy.paste(original,(x,y))
                original.putalpha(front)
                tile.paste(original,(x-box[0],y-box[1]))
            name = feature+'_'+state
            tile.save(OUT/(name+'.png'))
            skin[slot][state] = dict(copy.deepcopy(mesh),path=name)
            if state == 'neutral':
                rebuilt.alpha_composite(tile,box[:2])
    base.save(OUT/'reading_base.png')
    rebuilt.alpha_composite(base,tuple(offset))
    for name in ('fluke','shoe_far','shoe_near'):
        part=Image.open(KIT/(name+'.png'))
        rebuilt.alpha_composite(part,tuple(registration[name]['top_left']))
    assert ImageChops.difference(rebuilt.getchannel('A'),neutral.getchannel('A')).getbbox() is None
    for bg in ('#202536','#f2f0ed'):
        a,b = [Image.new('RGBA',neutral.size,bg) for _ in range(2)]
        a.alpha_composite(rebuilt); b.alpha_composite(neutral)
        assert ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox() is None
    save_json(OUT/'alignment.json',dict(canvas=neutral.size,reading_offset=offset,
              character_offset=registration['scene']['character_offset'],
              reference='v3 chin center (500,677), y down, bounds exclude right/bottom',slots=positions))
    save_json(OUT/'face_setup.json',skeleton)
    preview = Image.new('RGB',(780,244),'#e6ecf3')
    d=ImageDraw.Draw(preview)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',17)
    for i,im in enumerate((neutral,happy)):
        patch=im.crop((288,472,695,704)).resize((368,210),Image.Resampling.LANCZOS)
        preview.paste(patch,(10+390*i,3),patch)
        d.text((15+390*i,214),('中性 · 阅读','开心 · 偷着乐')[i],font=font,fill='#233449')
    preview.save(OUT/'comparison.jpg',quality=96)
    with ZipFile(ROOT/'docs/prone-v3-expressions.zip','w',ZIP_DEFLATED) as z:
        for f in sorted(OUT.iterdir()):
            if f.is_file() and f.name!='happy_source.png': z.write(f,f.name)
        for name in ('fluke','shoe_far','shoe_near','whale_cushion'): z.write(KIT/(name+'.png'),name+'.png')


if __name__ == '__main__':
    main()
