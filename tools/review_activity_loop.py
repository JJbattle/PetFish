"""Read existing activity captures, make review evidence and corrected GIFs.

Never edits the animator's source rig, scripts or original captures.
"""
from pathlib import Path
import json
from collections import Counter
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tools/_debug/activity_loop'
OUT=ROOT/'tools/_debug/activity_review'
DOC=ROOT/'docs/activity-review-20261106'
STEPS={'activity_neutral':100,'activity_ready':200,'activity_march_cycle':100,
       'activity_heel_cycle':150,'activity_relax':200}


def frames(scale,clip):
    paths=sorted((SRC/scale/clip).glob(f'{clip}_*.png'),
                 key=lambda p:float(p.stem.rsplit('_',1)[1]))
    # Last capture is the repeated closure pose, not an extra GIF frame.
    return [(p,Image.open(p).convert('RGBA')) for p in paths[:-1]]


def export_gif(scale,clip):
    items=frames(scale,clip)
    w,h=items[0][1].size
    # One palette for the whole animation prevents palette/dither flicker.
    training=Image.new('RGB',(128*8,128*((len(items)+7)//8)))
    for i,(_,im) in enumerate(items):
        thumb=im.copy();thumb.thumbnail((128,128))
        rgb=Image.new('RGB',thumb.size,'#eef2f6');rgb.paste(thumb,mask=thumb.getchannel('A'))
        training.paste(rgb,((i%8)*128,(i//8)*128))
    palette=training.quantize(colors=255,method=Image.Quantize.MEDIANCUT)
    colors=palette.getpalette()[:765]
    candidates=np.asarray(colors,dtype=np.int32).reshape(-1,3)
    black_index=int(np.argmin((candidates*candidates).sum(axis=1)))
    encoded=[]
    for _,im in items:
        indexed=np.asarray(im.convert('RGB').quantize(palette=palette,dither=Image.Dither.NONE)).copy()
        indexed[indexed==255]=black_index
        indices=(indexed.astype(np.uint16)+1).astype(np.uint8)
        indices[np.asarray(im)[:,:,3]<128]=0
        frame=Image.fromarray(indices).convert('P')
        frame.putpalette([0,0,0]+colors)
        frame.info['transparency']=0
        encoded.append(frame)
    folder=OUT/'corrected_gif'/scale;folder.mkdir(parents=True,exist_ok=True)
    path=folder/f'{clip}.gif'
    encoded[0].save(path,save_all=True,append_images=encoded[1:],
                    duration=STEPS[clip],loop=0,transparency=0,disposal=2,optimize=False)
    return path


def contact():
    pairs=[('招手：整臂旋转后藏进头发', 'activity_ready',.8,(300,390,750,690)),
           ('踏步：膝盖接缝与侧摆','activity_march_cycle',.5,(380,680,620,940)),
           ('踮脚：身体上移，仍是普通鞋','activity_heel_cycle',1.05,(380,680,620,940))]
    out=Image.new('RGB',(1500,690),'#e7edf3');d=ImageDraw.Draw(out)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',20)
    for i,(label,clip,t,rect) in enumerate(pairs):
        d.text((i*500+14,12),label,font=font,fill='#233d61')
        for row,tt in enumerate([0,t]):
            p=SRC/'zoom'/clip/f'{clip}_{tt:.3f}.png'
            im=Image.open(p).convert('RGBA').crop(rect)
            im.thumbnail((470,270),Image.Resampling.LANCZOS)
            bg=Image.new('RGBA',im.size,'#e7edf3');bg.alpha_composite(im)
            out.paste(bg.convert('RGB'),(i*500+15,60+row*310))
            d.text((i*500+14,335+row*310),f'{tt:.3f} s',font=font,fill='#233d61')
    out.save(DOC/'joint-evidence.jpg',quality=94)
    clip='activity_march_cycle'
    a=Image.open(SRC/'actual'/clip/f'{clip}_0.000.png').convert('RGBA')
    b=Image.open(SRC/'actual'/f'{clip}.gif').convert('RGBA')
    c=Image.open(OUT/'corrected_gif/actual'/f'{clip}.gif').convert('RGBA')
    panel=Image.new('RGB',(1100,450),'#e7edf3');d=ImageDraw.Draw(panel)
    for i,(label,im) in enumerate([('原始 PNG',a),('原 GIF 首帧',b),('透明索引修正后',c)]):
        tile=Image.new('RGBA',im.size,'#e7edf3');tile.alpha_composite(im)
        tile=tile.resize((306,306),Image.Resampling.NEAREST)
        panel.paste(tile.convert('RGB'),(i*365+20,70))
        d.text((i*365+25,22),label,font=font,fill='#233d61')
    panel.save(DOC/'gif-transparency.jpg',quality=94)
    aa=np.asarray(a)[:,:,3]>=128;bb=np.asarray(b)[:,:,3]>=128;cc=np.asarray(c)[:,:,3]>=128
    return {'png_opaque_pixels':int(aa.sum()),'original_gif_opaque_pixels':int(bb.sum()),
            'original_alpha_iou':float((aa&bb).sum()/(aa|bb).sum()),
            'corrected_alpha_iou':float((aa&cc).sum()/(aa|cc).sum())}


def main():
    DOC.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    for scale in ['zoom','actual']:
        for clip in STEPS:export_gif(scale,clip)
    data=json.loads((ROOT/'tools/_debug/activity_spine/activity_standing.spine-json').read_text())
    report={'gif':contact(),'attachment_types':dict(Counter(a.get('type','region')
           for s in data['skins'] for variants in s['attachments'].values() for a in variants.values())),
           'slots_by_bone':dict(Counter(s['bone'] for s in data['slots'])),
           'relax_has_slot_timeline':bool(data['animations']['activity_relax'].get('slots'))}
    assert report['gif']['corrected_alpha_iou']==1.0
    (DOC/'evidence.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
