"""Isolated pose-dependent knee outline experiment; no texture/source edits.

Adds local corrective controls to the animator's weighted leg meshes, keeping
the neutral pose, base bone motion and shoe contact unchanged.
"""
from pathlib import Path
import json
import math
import shutil
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'tools/_debug/activity_spine'
OUT=ROOT/'tools/_debug/activity_knee_corrective_spine'
NAME='activity_knee_corrective'


def smooth(a,b,x):
    t=max(0.,min(1.,(x-a)/(b-a)))
    return t*t*(3-2*t)


def sample(keys,t):
    for first,last in zip(keys,keys[1:]):
        if first.get('time',0)<=t<=last['time']:
            span=last['time']-first.get('time',0)
            u=(t-first.get('time',0))/span if span else 0
            return first.get('value',0)*(1-u)+last.get('value',0)*u
    return keys[-1].get('value',0) if keys else 0


def build():
    OUT.mkdir(parents=True,exist_ok=True)
    data=json.loads((SOURCE/'activity_standing.spine-json').read_text())
    bones=data['bones'];world={}
    for b in bones:
        px,py=world.get(b.get('parent'),(0,0))
        world[b['name']]=(px+b.get('x',0),py+b.get('y',0))
    base_names=[b['name'] for b in bones]
    children={}
    for side in ['l','r']:
        for parent in [f'thigh_{side}',f'calf_{side}']:
            name='art_knee_'+parent
            children[parent]=len(bones);bones.append({'name':name,'parent':parent})
    for side in ['l','r']:
        sx,sy=world[f'thigh_{side}']
        for mesh in data['skins'][0]['attachments'][f'thigh_{side}'].values():
            assert mesh['type']=='mesh'
            vertices=mesh['vertices'];result=[];i=0
            while i<len(vertices):
                count=int(vertices[i]);i+=1;entry=[]
                original=[vertices[i+j*4:i+(j+1)*4] for j in range(count)]
                i+=count*4
                idx,x,y,_=original[0];parent=base_names[int(idx)]
                wx,wy=world[parent];lx,ly=wx+x-sx,wy+y-sy
                outside=-lx if side=='l' else lx
                # Compact support: do not move the sock cuff or ankle pixels.
                mask=smooth(5,22,outside)*(1-smooth(5,32,abs(ly+63)))
                for idx,x,y,weight in original:
                    parent=base_names[int(idx)]
                    if weight*(1-mask)>1e-7:entry.append((idx,x,y,weight*(1-mask)))
                    if weight*mask>1e-7:entry.append((children[parent],x,y,weight*mask))
                total=sum(e[3] for e in entry)
                result.append(len(entry))
                for idx,x,y,weight in entry:result.extend([idx,x,y,weight/total])
            mesh['vertices']=result
    for clip,animation in data['animations'].items():
        tracks=animation.setdefault('bones',{})
        for side in ['l','r']:
            thigh=tracks.get(f'thigh_{side}',{}).get('rotate',[{'time':0,'value':0}])
            calf=tracks.get(f'calf_{side}',{}).get('rotate',[{'time':0,'value':0}])
            duration=max([k.get('time',0) for k in thigh+calf]+[0])
            times=[round(i/20,3) for i in range(round(duration*20)+1)] or [0]
            for part in ['thigh','calf']:
                keys=[]
                for t in times:
                    ta,ca=sample(thigh,t),sample(calf,t)
                    amplitude=17*min(abs(ca)/35,1)**1.4
                    dx=-amplitude if side=='l' else amplitude
                    theta=math.radians(ta+(ca if part=='calf' else 0))
                    keys.append({'time':t,'x':dx*math.cos(theta),'y':-dx*math.sin(theta)})
                tracks[f'art_knee_{part}_{side}']={'translate':keys}
    (OUT/f'{NAME}.spine-json').write_text(json.dumps(data,indent=2))
    atlas=(SOURCE/'activity_standing.atlas').read_text().splitlines();atlas[0]=NAME+'.png'
    (OUT/f'{NAME}.atlas').write_text('\n'.join(atlas)+'\n')
    shutil.copy2(SOURCE/'activity_standing.png',OUT/f'{NAME}.png')


def render():
    import activity_preview as p
    loop='--loop' in sys.argv
    actual='--actual' in sys.argv
    p.PROJECT=ROOT/'tools/_debug/activity_knee_corrective_proj'
    p.ACTIVITY_SPINE=OUT
    specs=','.join(f'activity_march_cycle:{t}' for t in [0,.25,.5,.75,1,1.25,1.5,1.75,2])
    specs+=',activity_heel_cycle:0.99,activity_heel_cycle:1,activity_heel_cycle:3.49,activity_heel_cycle:3.5'
    target='tools/_debug/activity_knee_corrective'
    if loop:target+='_loop_actual' if actual else '_loop'
    sys.argv=['activity_preview.py','--rig',NAME,
              '--loop' if loop else '--poses', 'activity_march_cycle:15:6' if loop else specs,
              '--out',target,'--scale','.2' if actual else '1','--no-diff']
    p.main()


def report():
    folder=ROOT/'tools/_debug/activity_knee_corrective'
    baseline=ROOT/'tools/_debug/activity_legmesh/final'
    doc=ROOT/'docs/activity-review-20261106'
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    report={'status':'isolated corrective prototype, not merged into animator builder',
            'source_textures_edited':False,'poses':{},'loops':{}}
    panel=Image.new('RGB',(1080,300),'#e7edf3');draw=ImageDraw.Draw(panel)
    for i,(label,path) in enumerate([
        ('原峰值',baseline/'activity_march_cycle_0.500.png'),
        ('局部修形峰值',folder/'activity_march_cycle_0.500.png'),
        ('中立不变',folder/'activity_march_cycle_0.000.png')]):
        im=Image.open(path).convert('RGBA').crop((420,725,600,825))
        bg=Image.new('RGBA',im.size,'#e7edf3');bg.alpha_composite(im)
        panel.paste(bg.resize((360,200)).convert('RGB'),(i*360,50))
        draw.text((i*360+10,15),label,font=font,fill='#233d61')
    panel.save(doc/'knee-corrective-prototype.jpg',quality=94)
    for t in ['0.000','0.500','1.500','2.000']:
        a=np.asarray(Image.open(folder/f'activity_march_cycle_{t}.png').convert('RGBA'))
        b=np.asarray(Image.open(baseline/f'activity_march_cycle_{t}.png').convert('RGBA'))
        changed=np.any(a!=b,axis=2)
        row={'changed_pixels':int(changed.sum()),
             'both_feet_below_y830_changed':int(changed[830:940].sum()),
             'left_outer_at_y762':int(np.where(a[762,420:530,3]>=128)[0].min()+420)}
        assert row['both_feet_below_y830_changed']==0
        if t in ['0.000','2.000']:assert row['changed_pixels']==0
        report['poses'][t]=row
    for scale,suffix in [('zoom','_loop'),('actual','_loop_actual')]:
        src=ROOT/f'tools/_debug/activity_knee_corrective{suffix}'
        paths=sorted(src.glob('activity_march_cycle_*.png'))
        assert len(paths)==91
        first=np.asarray(Image.open(paths[0]))
        diffs=[int(np.any(np.asarray(Image.open(paths[i]))!=first,axis=2).sum()) for i in [0,30,60,90]]
        max_delta=[int(np.abs(np.asarray(Image.open(paths[i])).astype(int)-first.astype(int)).max()) for i in [0,30,60,90]]
        # Subpixel float accumulation can change one 8-bit channel level in
        # zoom antialiasing; report it rather than claiming exact equality.
        assert max(max_delta)<=1
        frames=[]
        for path in paths[:-1]:
            im=Image.open(path).convert('RGBA')
            if scale=='zoom':
                im=im.crop((420,720,605,920)).resize((370,400),Image.Resampling.NEAREST)
            bg=Image.new('RGBA',im.size,'#e7edf3');bg.alpha_composite(im)
            frames.append(bg.convert('RGB'))
        training=Image.new('RGB',(128*10,128*9))
        for i,im in enumerate(frames):
            thumb=im.copy();thumb.thumbnail((128,128));training.paste(thumb,((i%10)*128,(i//10)*128))
        palette=training.quantize(colors=255,method=Image.Quantize.MEDIANCUT)
        indexed=[im.quantize(palette=palette,dither=Image.Dither.NONE) for im in frames]
        durations=[70,60,70]*30
        indexed[0].save(doc/f'knee-corrective-{scale}.gif',save_all=True,append_images=indexed[1:],
                        duration=durations,loop=0,disposal=2,optimize=False)
        report['loops'][scale]={'source_frames':91,'fps':15,'duration':6,
                                'boundary_pixel_diffs':diffs,'boundary_max_channel_delta':max_delta,
                                'method':'one continuously advanced loop state'}
    (doc/'knee-corrective-validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    if '--report' in sys.argv:
        report()
    else:
        build()
        if '--render' in sys.argv:render()
