"""Extract painted activity sheets and deliver registered, static Spine kits.

Imagegen supplies hidden artwork; this script only separates, registers and
packages attachments. It never changes production rigs or paints missing art.
"""
from pathlib import Path
import json
import math
import shutil
import zipfile
from collections import deque
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'assets/art/activity_spine_kit_v1'
FONT = 'C:/Windows/Fonts/msyh.ttc'


def extract(image, rect, path):
    part = image.crop(tuple(map(int, rect))).convert('RGBA')
    a = np.asarray(part).copy()
    # Only remove near-transparent generation haze, retain antialiased edges.
    alpha = a[:, :, 3]
    alpha[alpha < 24] = 0
    alpha[alpha > 240] = 255
    a[:, :, 3] = alpha
    part = Image.fromarray(a)
    # A neighbouring cell can contain a few pixels of another arm. Keep only
    # the largest connected attachment plus its two-pixel antialiased edge.
    pending = (alpha > 64).copy()
    groups = []
    hh, ww = pending.shape
    for yy, xx in zip(*np.where(pending)):
        if not pending[yy, xx]:
            continue
        q=deque([(int(xx),int(yy))]);pending[yy,xx]=False;points=[]
        while q:
            x0,y0=q.popleft();points.append((x0,y0))
            for nx,ny in ((x0-1,y0),(x0+1,y0),(x0,y0-1),(x0,y0+1)):
                if 0<=nx<ww and 0<=ny<hh and pending[ny,nx]:
                    pending[ny,nx]=False;q.append((nx,ny))
        groups.append(points)
    biggest=max(groups,key=len)
    mask=np.zeros((hh,ww),dtype=np.uint8)
    for x0,y0 in biggest:
        mask[y0,x0]=255
    mask=Image.fromarray(mask).filter(ImageFilter.MaxFilter(5))
    part.putalpha(ImageChops.multiply(part.getchannel('A'),mask))
    box = part.getchannel('A').point(lambda v: 255 if v > 64 else 0).getbbox()
    if box is None:
        raise ValueError(f'Empty part: {path}')
    box = (max(0, box[0]-3), max(0, box[1]-3),
           min(part.width, box[2]+3), min(part.height, box[3]+3))
    part = part.crop(box)
    padded = Image.new('RGBA', (part.width+24, part.height+24))
    padded.alpha_composite(part, (12, 12))
    path.parent.mkdir(parents=True, exist_ok=True)
    padded.save(path)
    return {'sheet_rect': list(rect), 'crop_bbox': list(box),
            'padding': 12, 'size': list(padded.size)}


def cut_sources():
    rows = {
        'common': ['head_front', 'head_turn_left', 'head_turn_right',
                   'head_closed', 'hair_back', 'tail'],
        'standing': ['body', 'arm_l', 'arm_r', 'leg_l_full', 'leg_r_full', None],
        'seated': ['body', 'arm_l', 'arm_r', 'leg_l_full', 'leg_r_full', 'chair'],
        'extra': ['head_left_step1', 'head_left_step2', 'head_right_step1',
                  'head_right_step2', 'heel_l_source', 'heel_r_source'],
    }
    manifest = {}
    for group, names in rows.items():
        image = Image.open(OUT/'sources'/f'{group}.png').convert('RGBA')
        cw, ch = image.width/3, image.height/2
        for i, name in enumerate(names):
            x, y = i % 3*cw, i//3*ch
            if name:
                key = f'{group}/{name}'
                manifest[key] = extract(image, (x,y,x+cw,y+ch), OUT/'parts'/f'{key}.png')
            else:
                for side in ('l', 'r'):
                    left = x if side == 'l' else x+cw/2
                    key = f'standing/arm_open_{side}'
                    manifest[key] = extract(image, (left,y,left+cw/2,y+ch), OUT/'parts'/f'{key}.png')
    (OUT/'extraction.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')


def split_derived():
    """Keep original local coordinates so overlaps reproduce the master."""
    def segment(key,name,lo,hi):
        im=Image.open(OUT/'parts'/f'{key}.png').convert('RGBA')
        mask=Image.new('L',im.size)
        ImageDraw.Draw(mask).rectangle((0,round(lo),im.width,round(hi)),fill=255)
        im.putalpha(ImageChops.multiply(im.getchannel('A'),mask))
        im.save(OUT/'parts'/f'{name}.png')
    for mode in ['standing','seated']:
        _,h=part_size(f'{mode}/body');waist=h*(.40 if mode=='standing' else .43)
        segment(f'{mode}/body',f'{mode}/bodice',0,waist+14)
        segment(f'{mode}/body',f'{mode}/skirt',waist-14,h)
        for side in ['l','r']:
            key=f'{mode}/leg_{side}_full';_,h=part_size(key)
            knee=h*.34;ankle=h*.73
            segment(key,f'{mode}/thigh_{side}',0,knee+14)
            segment(key,f'{mode}/calf_{side}',knee-14,ankle+14)
            segment(key,f'{mode}/shoe_{side}',ankle-14,h)
            if mode=='standing':
                segment(key,f'{mode}/calf_heel_{side}',knee-14,h*.68)
    for side in ['l','r']:
        im=Image.open(OUT/'parts/extra'/f'heel_{side}_source.png').convert('RGBA')
        # Remove the generated high sock cuff; use the existing calf's cuff.
        im=im.crop((0,round(im.height*.36),im.width,im.height))
        im.save(OUT/'parts/extra'/f'heel_{side}.png')


def layer(name, file, pivot, pos, scale=1.0, angle=0, bone=None, active=True):
    return dict(name=name, file=file, pivot=list(pivot), position=list(pos),
                scale=scale, angle=angle, bone=bone or name, active=active)


def part_size(key):
    return Image.open(OUT/'parts'/f'{key}.png').size


def normalized(name, key, height, pos, pivot=(.5, 0), **kw):
    w, h = part_size(key)
    return layer(name, key+'.png', (w*pivot[0],h*pivot[1]), pos, height/h, **kw)


def compose(layers, canvas=(1024,1024)):
    result = Image.new('RGBA', canvas)
    for item in layers:
        if not item.get('active',True):
            continue
        im = Image.open(OUT/'parts'/item['file']).convert('RGBA')
        scale = item['scale']
        size = (round(im.width*scale),round(im.height*scale))
        im = im.resize(size,Image.Resampling.LANCZOS)
        px,py = item['pivot'][0]*scale,item['pivot'][1]*scale
        extent = math.ceil(max(px,py,im.width-px,im.height-py))+8
        tile = Image.new('RGBA',(extent*2,extent*2))
        tile.alpha_composite(im,(round(extent-px),round(extent-py)))
        if item['angle']:
            tile = tile.rotate(-item['angle'],Image.Resampling.BICUBIC)
        result.alpha_composite(tile,(round(item['position'][0]-extent),round(item['position'][1]-extent)))
    return result


def build_layers(mode):
    layers=[]
    if mode == 'seated':
        layers.append(normalized('chair','seated/chair',390,(512,920),(.5,1)))
    layers.append(normalized('hair_back','common/hair_back',630,(512,130),(.5,0),bone='head'))
    layers.append(normalized('tail','common/tail',130,(630,700),(.08,.72),bone='hip'))
    for side,x in [('l',475),('r',549)]:
        for piece,bone in [('thigh','thigh'),('calf','calf'),('shoe','foot')]:
            layers.append(normalized(f'{piece}_{side}',f'{mode}/{piece}_{side}',230,(x,920),(.5,1),bone=f'{bone}_{side}'))
        if mode=='standing':
            layers.append(normalized(f'calf_heel_{side}',f'standing/calf_heel_{side}',230,(x,920),(.5,1),bone=f'calf_{side}',active=False))
            layers.append(normalized(f'heel_{side}','extra/heel_'+side,77,(x,920),(.5,.98),bone=f'foot_{side}',active=False))
    for name,bone in [('bodice','torso'),('skirt','hip')]:
        layers.append(normalized(name,f'{mode}/{name}',330,(512,424),(.5,0),bone=bone))
    for side,x in [('l',452),('r',572)]:
        pivot=(.72,.10) if side=='l' else (.28,.10)
        layers.append(normalized(f'arm_{side}',f'{mode}/arm_{side}',213,(x,457),pivot,bone=f'upper_arm_{side}'))
        layers.append(normalized(f'arm_open_{side}',f'standing/arm_open_{side}',213,(x,457),
                                 (.66,.12) if side=='l' else (.34,.12),bone=f'upper_arm_{side}',active=False))
    layers.append(normalized('head_front','common/head_front',450,(512,460),(.5,.91),bone='head'))
    for name in ['head_closed','head_turn_left','head_turn_right']:
        pivot_x = .44 if name.endswith('left') else .56 if name.endswith('right') else .5
        layers.append(normalized(name,'common/'+name,450,(512,460),(pivot_x,.91),bone='head',active=False))
    for side in ['left','right']:
        for step in [1,2]:
            name=f'head_{side}_step{step}'
            px=(.49 if step==1 else .46) if side=='left' else (.51 if step==1 else .54)
            layers.append(normalized(name,'extra/'+name,450,(512,460),(px,.91),bone='head',active=False))
    return layers


def setup_json(layers):
    # An editor-import setup with transform bones and REGION attachments.
    # Mesh/weights and animations are deliberately left to the animator.
    world={'root':(0,0),'hip':(512,650),'torso':(512,550),'head':(512,460)}
    parents={'hip':'root','torso':'hip','head':'torso'}
    for side,x in [('l',475),('r',549)]:
        for name,pos,parent in [(f'thigh_{side}',(x,705),'hip'),
                                (f'calf_{side}',(x,768),f'thigh_{side}'),
                                (f'foot_{side}',(x,858),f'calf_{side}')]:
            world[name]=pos;parents[name]=parent
    for side,x in [('l',452),('r',572)]:
        sign=-1 if side=='l' else 1
        for name,pos,parent in [(f'upper_arm_{side}',(x,457),'torso'),
                               (f'forearm_{side}',(x+sign*28,544),f'upper_arm_{side}'),
                               (f'hand_{side}',(x+sign*52,606),f'forearm_{side}')]:
            world[name]=pos;parents[name]=parent
    world['chair']=(512,920);parents['chair']='root'
    bones=[dict(name='root')]
    for name,(x,y) in world.items():
        if name=='root':continue
        parent=parents[name];px,py=world[parent]
        bones.append(dict(name=name,parent=parent,x=x-px,y=-(y-py)))
    slots=[]
    attachments={}
    for item in layers:
        bone=item['bone']
        name=item['name']
        slot_name='head' if name.startswith('head_') else name
        if name.startswith('arm_open_'):slot_name='arm_'+name[-1]
        if name.startswith('heel_'):slot_name='shoe_'+name[-1]
        if name.startswith('calf_heel_'):slot_name='calf_'+name[-1]
        if slot_name not in attachments:
            slots.append(dict(name=slot_name,bone=bone,**({'attachment':name} if item['active'] else {})))
            attachments[slot_name]={}
        w,h=part_size(item['file'][:-4]);px,py=item['pivot'];s=item['scale']
        bx,by=world[bone]
        attachments[slot_name][name]=dict(type='region',path=item['file'][:-4],
            x=item['position'][0]-bx+(w/2-px)*s,y=-(item['position'][1]-by)-(h/2-py)*s,
            width=w*s,height=h*s,rotation=-item['angle'])
    return dict(skeleton=dict(spine='4.2.43',x=0,y=-1024,width=1024,height=1024,images='../parts/'),
                bones=bones,slots=slots,skins=[dict(name='default',attachments=attachments)],animations={})


def save_mode(mode):
    folder=OUT/mode;folder.mkdir(exist_ok=True)
    layers=build_layers(mode)
    manifest=dict(version=1,canvas=[1024,1024],coordinates='top-left; y down; clockwise degrees',
                  status='static assembly; unweighted region setup; no animations',layers=layers)
    (folder/'assembly.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    (folder/'setup.spine-json').write_text(json.dumps(setup_json(layers),indent=2),encoding='utf-8')
    (folder/'setup.json').write_text(json.dumps(setup_json(layers),indent=2),encoding='utf-8')
    im=compose(layers);im.save(folder/'assembled.png')
    for color,name in [('#eef2f6','assembled-light.jpg'),('#242934','assembled-dark.jpg')]:
        bg=Image.new('RGBA',im.size,color);bg.alpha_composite(im)
        bg.convert('RGB').save(folder/name,quality=94)
    # Human-readable joint locations; JSON bones are a static starting point.
    annotated=Image.new('RGBA',im.size,'#eef2f6');annotated.alpha_composite(im)
    d=ImageDraw.Draw(annotated);font=ImageFont.truetype(FONT,14)
    setup=setup_json(layers);world={'root':(0,0)}
    for b in setup['bones'][1:]:
        px,py=world[b['parent']];x,y=px+b['x'],py-b['y'];world[b['name']]=(x,y)
        if b['parent']!='root':d.line((px,py,x,y),fill='#e75d55',width=2)
        d.ellipse((x-4,y-4,x+4,y+4),fill='#ffd35c',outline='#142747')
        d.text((x+7,y-17),b['name'],font=font,fill='#cf3e3e',stroke_width=1,stroke_fill='white')
    annotated.convert('RGB').save(folder/'binding-landmarks.jpg',quality=94)
    # Show all head alternatives on the real assembled body, not floating.
    heads=['head_front','head_left_step1','head_left_step2','head_turn_left',
           'head_closed','head_right_step1','head_right_step2','head_turn_right']
    sheet=Image.new('RGB',(1600,900),'#e4eaf1');draw=ImageDraw.Draw(sheet)
    for i,name in enumerate(heads):
        variant=[dict(l) for l in layers]
        for l in variant:
            if l['name'].startswith('head_'):l['active']=l['name']==name
        shot=compose(variant);shot.thumbnail((390,410),Image.Resampling.LANCZOS)
        x,y=(i%4)*400,(i//4)*450
        sheet.paste(shot,(x+(400-shot.width)//2,y),shot)
        draw.text((x+8,y+418),name,font=font,fill='#233d61')
    sheet.save(folder/'head-variants-check.jpg',quality=94)
    if mode=='standing':
        for tag in ['open-arms','heels']:
            variant=[dict(l) for l in layers]
            for l in variant:
                n=l['name']
                if tag=='open-arms' and n.startswith('arm_'):
                    l['active']=n.startswith('arm_open_')
                if tag=='heels' and n.startswith(('calf_','shoe_','heel_')):
                    l['active']=n.startswith(('calf_heel_','heel_'))
            shot=compose(variant);bg=Image.new('RGBA',shot.size,'#eef2f6');bg.alpha_composite(shot)
            bg.convert('RGB').save(folder/f'{tag}-check.jpg',quality=94)


def overview():
    paths=sorted((OUT/'parts').rglob('*.png'))
    tilew,tileh=280,330
    sheet=Image.new('RGB',(tilew*6,tileh*math.ceil(len(paths)/6)), '#e4eaf1')
    d=ImageDraw.Draw(sheet);font=ImageFont.truetype(FONT,15)
    for i,path in enumerate(paths):
        im=Image.open(path).convert('RGBA');im.thumbnail((260,280),Image.Resampling.LANCZOS)
        x,y=(i%6)*tilew,(i//6)*tileh
        sheet.paste(im,(x+(tilew-im.width)//2,y+(280-im.height)//2),im)
        d.text((x+8,y+291),str(path.relative_to(OUT/'parts')),font=font,fill='#233d61')
    sheet.save(OUT/'parts-overview.jpg',quality=94)


def validate_and_package():
    report={'png_files':0,'setups':{},'status':'static artwork/JSON checks only; not Spine editor/runtime validation'}
    for path in (OUT/'parts').rglob('*.png'):
        im=Image.open(path)
        assert im.mode=='RGBA',path
        alpha=np.asarray(im)[:,:,3]
        assert alpha.max()==255 and alpha.min()==0,path
        assert int((alpha>128).sum())>100,path
        report['png_files']+=1
    for mode in ['standing','seated']:
        path=OUT/mode/'setup.spine-json';data=json.loads(path.read_text())
        seen=set();world={}
        for bone in data['bones']:
            if 'parent' in bone:assert bone['parent'] in seen,bone
            seen.add(bone['name'])
        attachments=data['skins'][0]['attachments'];slot_names=set()
        for slot in data['slots']:
            assert slot['name'] not in slot_names
            slot_names.add(slot['name']);assert slot['bone'] in seen
            if 'attachment' in slot:assert slot['attachment'] in attachments[slot['name']]
        for variants in attachments.values():
            for region in variants.values():
                assert (OUT/'parts'/(region['path']+'.png')).exists(),region['path']
        report['setups'][mode]={'bones':len(seen),'slots':len(data['slots']),
                                'regions':sum(len(v) for v in attachments.values()),'animations':0}
    (OUT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    archive=ROOT/'docs/activity-spine-complete-kit-v1.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
        for path in OUT.rglob('*'):
            if path.is_file():z.write(path,path.relative_to(ROOT).as_posix())
        z.write(ROOT/'SPINE_ACTIVITY_HANDOFF.md','SPINE_ACTIVITY_HANDOFF.md')
        z.write(ROOT/'tools/prepare_activity_kit.py','tools/prepare_activity_kit.py')
        for folder in ['standing_activity_v1','seated_neck_shoulder_v1']:
            for path in (ROOT/'assets/art'/folder).glob('*'):
                if path.is_file():z.write(path,path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    print(json.dumps(report,indent=2))
    print(archive,archive.stat().st_size)


if __name__ == '__main__':
    cut_sources()
    split_derived()
    for mode in ['standing','seated']:
        save_mode(mode)
    overview()
    validate_and_package()
    print(json.dumps({p.parent.name+'/'+p.stem:Image.open(p).size for p in (OUT/'parts').rglob('*.png')},indent=2))
