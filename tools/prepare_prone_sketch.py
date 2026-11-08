"""Assemble the drawing pose from painted attachments and the seated whale."""
import json
import math
import shutil
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

from PIL import Image
from prepare_rest_kit import positioned

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'assets/art/prone_sketch_v1'
KIT = ART / 'kit'
WHALE = ROOT / 'assets/art/whale_seated_work_v2/kit/whale_cushion.png'
CANVAS = (1600, 1040)
# Angles below are adjustments around the shoulder. The set-up angle is baked
# into the attachment, so animation keys start and end at zero.
STROKES = [(0, 0), (.4, -.9), (.75, .55), (1.1, -.5), (1.4, .25),
           (1.95, .25), (2.35, -.7), (2.7, .45), (3, 0)]


def cut(sheet, rect, name):
    im = sheet.crop(rect)
    l,t,r,b = im.getchannel('A').point(lambda a: 255 if a > 20 else 0).getbbox()
    # Include antialiased edges around the visible silhouette.
    box = (max(rect[0],rect[0]+l-4), max(rect[1],rect[1]+t-4),
           min(rect[2],rect[0]+r+4), min(rect[3],rect[1]+b+4))
    sheet.crop(box).save(KIT/(name+'.png'))
    return box[:2]


def build():
    KIT.mkdir(exist_ok=True)
    sheet = Image.open(ART/'sheet_without_cushion.png').convert('RGBA')
    assert sheet.size == (1536,1024)
    bx,by = cut(sheet,(0,0,1190,1024),'body_pad')
    ax,ay = cut(sheet,(1200,450,1536,1024),'drawing_arm')
    shutil.copyfile(WHALE,KIT/'whale_cushion.png')
    layers = [
        ('whale_cushion',(0,0),(15,367),.96,0),
        ('body_pad',(0,0),(380+bx,by),1,0),
        ('drawing_arm',(1395-ax,535-ay),(1040,650),.666,19),
    ]
    def composite(delta):
        canvas = Image.new('RGBA',CANVAS)
        for name,pivot,at,scale,angle in layers:
            with Image.open(KIT/(name+'.png')) as part:
                tile, xy = positioned(part,pivot,at,scale,angle + (delta if name=='drawing_arm' else 0))
                canvas.alpha_composite(tile,xy)
        return canvas
    assembled = composite(0)
    assembled.save(KIT/'assembled.png')
    bbox = assembled.getchannel('A').point(lambda a:255 if a>24 else 0).getbbox()
    preview = Image.new('RGBA',CANVAS,'#e6ecf3')
    preview.alpha_composite(assembled)
    crop = preview.crop(bbox)
    crop.thumbnail((840,560),Image.Resampling.LANCZOS)
    crop.convert('RGB').save(KIT/'preview.jpg',quality=95)
    setup = {'skeleton':{'spine':'4.2.43','images':'./','width':CANVAS[0],'height':CANVAS[1],'y':-CANVAS[1]},
             'bones':[{'name':'root'}],'slots':[],'skins':[{'name':'default','attachments':{}}],
             'animations':{'prone_sketch_loop':{'bones':{'drawing_arm':{
                 'rotate':[{'time':time,'value':-a} for time,a in STROKES]}}}}}
    registration = []
    for name,pivot,at,scale,angle in layers:
        with Image.open(KIT/(name+'.png')) as part:
            w,h = part.size
        setup['bones'].append({'name':name,'parent':'root','x':at[0],'y':-at[1]})
        setup['slots'].append({'name':name,'bone':name,'attachment':name})
        tilt = math.radians(angle)
        dx,dy = (w/2-pivot[0])*scale,(h/2-pivot[1])*scale
        region = dict(type='region',path=name,width=w*scale,height=h*scale,
                      x=dx*math.cos(tilt)-dy*math.sin(tilt),
                      y=-(dx*math.sin(tilt)+dy*math.cos(tilt)),rotation=-angle)
        setup['skins'][0]['attachments'][name] = {name:region}
        registration.append(dict(name=name,pivot=pivot,position=at,scale=scale,angle_cw=angle))
    data = dict(canvas=CANVAS,visible_bbox=bbox,draw_order_back_to_front=registration,
                reference='canvas top left; x right, y down; uniform scale')
    (KIT/'assembly.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    (KIT/'sketch_setup.json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
    arm = layers[-1]
    for _,delta in STROKES:
        a = math.radians(arm[4]+delta)
        dx,dy=(1236-1395)*arm[3],(928-535)*arm[3]
        x,y=arm[2][0]+dx*math.cos(a)-dy*math.sin(a),arm[2][1]+dx*math.sin(a)+dy*math.cos(a)
        assert 830<x<885 and 835<y<885,(x,y)
    assert (KIT/'whale_cushion.png').read_bytes()==WHALE.read_bytes()
    archive = ROOT/'docs/prone-sketch-whale-kit.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for f in sorted(KIT.iterdir()):
            if f.is_file(): z.write(f,f.name)
    with ZipFile(archive) as z: assert z.testzip() is None


if __name__=='__main__':
    build()
