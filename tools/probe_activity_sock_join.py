"""Isolated same-art continuous ankle skinning prototype.

Preserves source textures, base animation and foot contact. Both shoe slots
remain separate; normal/heel use one artwork with shared calf/foot weighting.
"""
from pathlib import Path
import copy
import json
import math
import sys
from PIL import Image, ImageDraw, ImageFont
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
SRC=ROOT/'tools/_debug/activity_spine'
OUT=ROOT/'tools/_debug/activity_sock_join_spine'
NAME='activity_sock_join'


def smooth(y):
    t=max(0.,min(1.,(y-858)/37))
    return t*t*(3-2*t)


def build():
    import build_activity_spine as builder
    OUT.mkdir(parents=True,exist_ok=True)
    data=json.loads((SRC/'activity_standing.spine-json').read_text())
    world=builder.compute_world(data['bones'])
    names=[b['name'] for b in data['bones']];index={n:i for i,n in enumerate(names)}
    lines=(SRC/'activity_standing.atlas').read_text().splitlines()
    rects={};current=None
    for line in lines[5:]:
        if line and not line.startswith(' '):current=line;rects[current]={}
        elif current and ':' in line:
            k,v=line.strip().split(':',1);rects[current][k]=v.strip()
    page=Image.open(SRC/'activity_standing.png').convert('RGBA');textures={}
    for name,r in rects.items():
        x,y=map(int,r['xy'].split(','));w,h=map(int,r['size'].split(','))
        textures[name]=page.crop((x,y,x+w,y+h))
    skin=data['skins'][0]['attachments']
    for side in ['l','r']:
        calf=f'calf_{side}';foot=f'foot_{side}'
        fx,fy=world[foot]
        leg=copy.deepcopy(skin[f'thigh_{side}'][f'leg_{side}'])
        verts=leg['vertices'];result=[];i=0
        while i<len(verts):
            count=int(verts[i]);i+=1;entries=[]
            for j in range(count):
                bi,x,y,w=verts[i+j*4:i+(j+1)*4]
                bx,by=world[names[int(bi)]];wx,wy=bx+x,by+y
                t=smooth(-wy)
                if w*(1-t)>1e-8:entries.append((bi,x,y,w*(1-t)))
                if w*t>1e-8:entries.append((index[foot],wx-fx,wy-fy,w*t))
            i+=count*4;result.append(len(entries))
            for entry in entries:result.extend(entry)
        leg['vertices']=result
        skin[f'thigh_{side}'][f'leg_{side}']=leg
        skin[f'thigh_{side}'][f'leg_heel_{side}']=copy.deepcopy(leg)
        # Keep the ordinary leg's uncut sock edge and original painted colour.
        textures[f'leg_heel_{side}']=textures[f'leg_{side}'].copy()
        region=skin[f'shoe_{side}'][f'shoe_{side}']
        w,h=region['width'],region['height'];cx,cy=region['x'],region['y']
        cols=math.ceil(w/5)+1;rows=math.ceil(h/5)+1
        uv=[];vertices=[];triangles=[]
        for j in range(rows):
            v=j/(rows-1)
            for i in range(cols):
                u=i/(cols-1);uv.extend((u,v))
                wx,wy=fx+cx+(u-.5)*w,fy+cy+(.5-v)*h
                t=smooth(-wy);entries=[]
                for bone,weight in [(calf,1-t),(foot,t)]:
                    if weight<=1e-8:continue
                    bx,by=world[bone];entries.append((index[bone],wx-bx,wy-by,weight))
                vertices.append(len(entries))
                for entry in entries:vertices.extend(entry)
        for j in range(rows-1):
            for i in range(cols-1):
                a=j*cols+i;triangles.extend((a,a+cols,a+cols+1,a,a+cols+1,a+1))
        mesh={'type':'mesh','uvs':uv,'triangles':triangles,'vertices':vertices,'width':w,'height':h}
        for attachment in [f'shoe_{side}',f'heel_{side}']:
            skin[f'shoe_{side}'][attachment]=copy.deepcopy(mesh)
            textures[attachment]=textures[f'standing/shoe_{side}'].copy()
    placements,size=builder.shelf_pack(list(textures.items()));page=Image.new('RGBA',size)
    atlas=[NAME+'.png','size: %d,%d'%size,'format: RGBA8888','filter: Linear,Linear','repeat: none']
    for name,x,y,w,h in placements:
        page.paste(textures[name],(x,y))
        atlas.extend([name,'  rotate: false',f'  xy: {x}, {y}',f'  size: {w}, {h}',f'  orig: {w}, {h}','  offset: 0, 0','  index: -1'])
    # Hold the exact same bone pose while only the attachment names change.
    data['animations']['activity_sock_switch_probe']={
        'bones':{'hip':{'translate':[{'time':0,'x':0,'y':5}]},
                 'foot_l':{'translate':[{'time':0,'x':0,'y':-5}]},
                 'foot_r':{'translate':[{'time':0,'x':0,'y':-5}]}},
        'slots':{f'thigh_{s}':{'attachment':[{'time':0,'name':f'leg_{s}'},{'time':1,'name':f'leg_heel_{s}'}]} for s in ['l','r']}}
    for s in ['l','r']:
        data['animations']['activity_sock_switch_probe']['slots'][f'shoe_{s}']={
            'attachment':[{'time':0,'name':f'shoe_{s}'},{'time':1,'name':f'heel_{s}'}]}
    page.save(OUT/f'{NAME}.png')
    (OUT/f'{NAME}.atlas').write_text('\n'.join(atlas)+'\n')
    (OUT/f'{NAME}.spine-json').write_text(json.dumps(data,indent=2))


def render():
    import activity_preview as p
    loop='--loop' in sys.argv;actual='--actual' in sys.argv
    p.PROJECT=ROOT/'tools/_debug/activity_sock_join_proj'
    p.ACTIVITY_SPINE=OUT
    specs=','.join('activity_heel_cycle:'+str(t) for t in [0,.5,.99,1,1.01,2,3.49,3.5,3.51,4])
    specs+=',activity_march_cycle:0,activity_march_cycle:0.5,activity_march_cycle:1.5,activity_march_cycle:2'
    specs+=',activity_sock_switch_probe:0.99,activity_sock_switch_probe:1,activity_sock_switch_probe:1.01'
    target='tools/_debug/activity_sock_join'
    if loop:target+='_loop_actual' if actual else '_loop'
    sys.argv=['activity_preview.py','--rig',NAME,'--loop' if loop else '--poses',
              'activity_heel_cycle:15:12' if loop else specs,
              '--scale','.2' if actual else '1','--out',target,'--no-diff']
    p.main()


def report():
    folder=ROOT/'tools/_debug/activity_sock_join'
    doc=ROOT/'docs/activity-review-20261106'
    measurements=[]
    for t in ['0.000','0.990','1.000','1.010','2.000','3.490','3.500','3.510','4.000']:
        image=Image.open(folder/f'activity_heel_cycle_{t}.png').convert('RGBA');a=np.asarray(image)
        feet={}
        for side,x0,x1 in [('l',410,512),('r',512,615)]:
            ys,xs=np.where(a[830:940,x0:x1,3]>=128)
            feet[side]={'ground_y':int(ys.max()+830),'contact_x':float(np.median(xs[ys>=ys.max()-2])+x0)}
        measurements.append({'time':t,'feet':feet})
    for m in measurements:
        assert m['feet']==measurements[0]['feet']
    switch=[]
    ref=np.asarray(Image.open(folder/'activity_sock_switch_probe_0.990.png').convert('RGBA'))
    for t in ['0.990','1.000','1.010']:
        a=np.asarray(Image.open(folder/f'activity_sock_switch_probe_{t}.png').convert('RGBA'))
        switch.append(int(np.any(a!=ref,axis=2).sum()))
    assert switch==[0,0,0]
    proof={'status':'isolated prototype; no changes merged into animator builder',
           'contact':measurements,'same_pose_switch_pixel_diffs':switch,
           'source_pngs_modified':False,'base_animation_modified':False}
    panel=Image.new('RGB',(1080,440),'#e7edf3');d=ImageDraw.Draw(panel)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    items=[('现有切换前',ROOT/'tools/_debug/activity_knee_r2/heel_zoom/activity_heel_cycle_0.990.png'),
           ('现有切换后',ROOT/'tools/_debug/activity_knee_r2/heel_zoom/activity_heel_cycle_1.000.png'),
           ('同源原画连续踝部',folder/'activity_heel_cycle_1.000.png')]
    for i,(label,path) in enumerate(items):
        image=Image.open(path).convert('RGBA').crop((410,780,615,935))
        bg=Image.new('RGBA',image.size,'#e7edf3');bg.alpha_composite(image)
        panel.paste(bg.resize((328,248)).convert('RGB'),(i*360+15,45))
        d.text((i*360+15,10),label,font=font,fill='#233d61')
    d.text((18,325),'同一骨骼姿态只切附件：像素差 0；鞋底/接触横坐标保持不变',font=font,fill='#233d61')
    d.text((18,370),'原动画参数和源 PNG 未改动；鞋 slot 继续独立保留',font=font,fill='#233d61')
    panel.save(doc/'sock-join-comparison.jpg',quality=94)
    for scale,suffix in [('zoom','_loop'),('actual','_loop_actual')]:
        src=ROOT/f'tools/_debug/activity_sock_join{suffix}'
        paths=sorted(src.glob('activity_heel_cycle_*.png'));assert len(paths)==181
        first=np.asarray(Image.open(paths[0]))
        delta=[int(np.abs(np.asarray(Image.open(paths[i])).astype(int)-first.astype(int)).max()) for i in [0,60,120,180]]
        frames=[]
        for path in paths[:-1]:
            image=Image.open(path).convert('RGBA')
            if scale=='zoom':image=image.crop((410,735,615,935)).resize((410,400),Image.Resampling.NEAREST)
            bg=Image.new('RGBA',image.size,'#e7edf3');bg.alpha_composite(image);frames.append(bg.convert('RGB'))
        train=Image.new('RGB',(128*12,128*15))
        for i,image in enumerate(frames):
            thumb=image.copy();thumb.thumbnail((128,128));train.paste(thumb,((i%12)*128,(i//12)*128))
        palette=train.quantize(colors=255,method=Image.Quantize.MEDIANCUT)
        frames=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
        frames[0].save(doc/f'sock-join-{scale}.gif',save_all=True,append_images=frames[1:],
                       duration=[70,60,70]*60,disposal=2,loop=0,optimize=False)
        proof[scale+'_loop']={'source_frames':181,'fps':15,'seconds':12,'boundary_max_channel_delta':delta}
    (doc/'sock-join-validation.json').write_text(json.dumps(proof,indent=2),encoding='utf-8')
    print(json.dumps(proof,indent=2))


if __name__=='__main__':
    if '--report' in sys.argv:report()
    else:
        build()
        if '--render' in sys.argv:render()
