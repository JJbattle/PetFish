"""Register redrawn heel art against the measured ground without touching v1.

Consumes the animator's current debug export (including weighted sleeves),
replaces only two heel textures/regions, and renders in a separate project.
"""
from pathlib import Path
import json
import hashlib
import sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
KIT=ROOT/'assets/art/activity_spine_kit_v2'
SOURCE=ROOT/'tools/_debug/activity_spine'
OUT=ROOT/'tools/_debug/activity_artfix_spine'
NAME='activity_standing_artfix'


def build():
    KIT.mkdir(exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    source=SOURCE/'activity_standing.spine-json'
    data=json.loads(source.read_text(encoding='utf-8'))
    import prepare_activity_kit
    import build_activity_spine
    src=Image.open(KIT/'heel_front_source.png').convert('RGBA')
    new_images={};changes=[]
    atlas_lines=(SOURCE/'activity_standing.atlas').read_text(encoding='utf-8').splitlines()
    old_page=Image.open(SOURCE/'activity_standing.png').convert('RGBA')
    atlas={};current=None
    for line in atlas_lines[5:]:
        if line and not line.startswith(' '):
            current=line;atlas[current]={}
        elif current and ':' in line:
            key,value=line.strip().split(':',1);atlas[current][key]=value.strip()
    textures={}
    for name,rect in atlas.items():
        x,y=map(int,rect['xy'].split(','));w,h=map(int,rect['size'].split(','))
        textures[name]=old_page.crop((x,y,x+w,y+h))
    baseline=Image.open(ROOT/'tools/_debug/activity_probe/activity_probe_toe_0.000.png').convert('RGBA')
    base_alpha=np.asarray(baseline)[:,:,3]
    for i,side in enumerate(['l','r']):
        path=KIT/f'heel_{side}.png'
        prepare_activity_kit.extract(src,(i*src.width/2,0,(i+1)*src.width/2,src.height),path)
        new=Image.open(path).convert('RGBA')
        # An open sock join is not a drawn cuff: trim the generated dark top
        # outline within the existing calf overlap, without painting pixels.
        pixels=np.asarray(new).copy();alpha=pixels[:,:,3]
        top=int(np.where(alpha>=128)[0].min())
        ramp=np.clip((np.arange(new.height)-(top+16))/6,0,1)
        pixels[:,:,3]=(alpha*ramp[:,None]).astype(np.uint8)
        new=Image.fromarray(pixels);new.save(path)
        att=data['skins'][0]['attachments'][f'shoe_{side}'][f'heel_{side}']
        old=dict(att)
        normal=textures[f'standing/shoe_{side}']
        original_width=normal.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
        desired_width=original_width[2]-original_width[0]
        visible=new.getchannel('A').point(lambda a:255 if a>=128 else 0).getbbox()
        scale=desired_width/(visible[2]-visible[0])
        w,h=round(new.width*scale),round(new.height*scale)
        rendered=new.resize((w,h),Image.Resampling.LANCZOS)
        alpha=np.asarray(rendered)[:,:,3]
        ys,xs=np.where(alpha>=128);bottom=int(ys.max());contact=float(np.median(xs[ys>=bottom-2]))
        x0,x1=(410,512) if side=='l' else (512,615)
        yy,xx=np.where(base_alpha[830:940,x0:x1]>=128)
        ground=int(yy.max()+830);target_x=float(np.median(xx[yy>=yy.max()-2])+x0)
        bx=475 if side=='l' else 549;by=858
        att.update(x=round(target_x-bx-contact+w/2,4),
                   y=round(by+bottom-h/2-ground,4),width=w,height=h)
        textures[att['path']]=rendered
        changes.append(dict(slot=f'shoe_{side}',attachment=f'heel_{side}',
                            path=att['path'],source_png=path.name,region=dict(att),
                            old_region=old,target_ground_y=ground,target_contact_x=target_x,
                            png_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    placements,size=build_activity_spine.shelf_pack(list(textures.items()))
    page=Image.new('RGBA',size)
    atlas=[NAME+'.png','size: %d,%d'%size,'format: RGBA8888','filter: Linear,Linear','repeat: none']
    for name,x,y,w,h in placements:
        page.paste(textures[name],(x,y))
        atlas.extend([name,'  rotate: false',f'  xy: {x}, {y}',f'  size: {w}, {h}',f'  orig: {w}, {h}', '  offset: 0, 0','  index: -1'])
    page.save(OUT/f'{NAME}.png')
    (OUT/f'{NAME}.atlas').write_text('\n'.join(atlas)+'\n',encoding='utf-8')
    (OUT/f'{NAME}.spine-json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    patch=dict(issue='ART-HEEL-01',date='2026-11-07',
               kind='redrawn front-facing heel shoes plus attachment registration',
               applies_to='standing shoe_l/heel_l and shoe_r/heel_r; +y is up in Spine',
               source_skeleton_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
               alpha_threshold=128,changes=changes,
               status='awaiting isolated render verification')
    (KIT/'ART_HEEL_01.json').write_text(json.dumps(patch,indent=2),encoding='utf-8')


def render():
    import activity_preview
    activity_preview.PROJECT=ROOT/'tools/_debug/activity_artfix_preview_proj'
    activity_preview.ACTIVITY_SPINE=OUT
    sys.argv=['activity_preview.py','--rig',NAME,'--poses',
              'activity_probe_toe:0,activity_probe_toe:0.49,activity_probe_toe:0.5,activity_probe_toe:1,activity_probe_toe:1.49,activity_probe_toe:1.5,activity_probe_toe:2',
              '--out','tools/_debug/activity_artfix_probe','--no-diff']
    activity_preview.main()


def verify():
    folder=ROOT/'tools/_debug/activity_artfix_probe'
    records=[]
    for time in ['0.000','0.490','0.500','1.000','1.490','1.500','2.000']:
        alpha=np.asarray(Image.open(folder/f'activity_probe_toe_{time}.png').convert('RGBA'))[:,:,3]
        feet={}
        for side,x0,x1,cx in [('l',410,512,475),('r',512,615,549)]:
            ys,xs=np.where(alpha[830:940,x0:x1]>=128)
            feet[side]={'sole_y':int(ys.max()+830),
                        'bottom_band_median_x':float(np.median(xs[ys>=ys.max()-2])+x0),
                        'ankle_center_gap_rows':[int(y) for y in range(810,891) if alpha[y,cx]<25]}
        records.append({'time':float(time),'feet':feet})
    for side in ['l','r']:
        base=records[0]['feet'][side]
        for r in records:
            assert r['feet'][side]['sole_y']==base['sole_y']
            assert abs(r['feet'][side]['bottom_band_median_x']-base['bottom_band_median_x'])<=.5
            assert not r['feet'][side]['ankle_center_gap_rows']
    report={'status':'contact and ankle continuity passed for seven sampled frames',
            'alpha_threshold':128,'contact_definition':'bottom 3-row opaque band median; visible sole max-y',
            'scope':'not a full animation/biomechanical approval','samples':records}
    (KIT/'validation.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    patch=json.loads((KIT/'ART_HEEL_01.json').read_text())
    patch['status']=report['status']
    (KIT/'ART_HEEL_01.json').write_text(json.dumps(patch,indent=2),encoding='utf-8')
    canvas=Image.new('RGB',(1110,600),'#e7edf3');draw=ImageDraw.Draw(canvas)
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',19)
    paths=[('普通站立',ROOT/'tools/_debug/activity_probe/activity_probe_toe_0.000.png'),
           ('旧提踵鞋：外撇、下穿',ROOT/'tools/_debug/activity_probe/activity_probe_toe_0.500.png'),
           ('v2：正面鞋、接地点注册',folder/'activity_probe_toe_0.500.png')]
    for i,(label,path) in enumerate(paths):
        image=Image.open(path).convert('RGBA').crop((410,780,615,935))
        bg=Image.new('RGBA',image.size,'#e7edf3');bg.alpha_composite(image)
        bg=bg.resize((328,248),Image.Resampling.NEAREST)
        canvas.paste(bg.convert('RGB'),(i*370+16,55))
        draw.text((i*370+14,15),label,font=font,fill='#233d61')
        draw.line((i*370+16,55+(911-780)*1.6,i*370+344,55+(911-780)*1.6),fill='#dd645c',width=1)
    draw.text((18,330),'同一地面；v2 保持脚尖轮廓位置，未覆盖原素材或动画脚本',font=font,fill='#233d61')
    draw.text((18,375),'核查范围：7 个关键时刻的鞋底高度、接触横坐标、袜踝中心线连续性',font=font,fill='#233d61')
    draw.text((18,420),'后续仍需检查：附件切换瞬间、完整提踵循环、实际尺寸辨识度',font=font,fill='#233d61')
    canvas.save(KIT/'heel-comparison.jpg',quality=94)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    build()
    if '--render' in sys.argv:
        render()
        verify()
