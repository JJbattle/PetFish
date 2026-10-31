"""Extract requested transparent attachments and reproduce the seated setup.

Art is painted with imagegen; this only cuts, registers and packs those assets.
Never modifies the production rig. Run from the repository root.
"""
import json
from collections import deque
from pathlib import Path
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont
from prepare_rest_kit import positioned

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / 'assets/art/whale_seated_work_v1'
OUT = SRC / 'kit'


def save_part(image, name, mask=None):
    if mask is not None:
        image = image.copy()
        image.putalpha(ImageChops.multiply(image.getchannel('A'), mask))
    box = image.getchannel('A').point(lambda a: 255 if a > 24 else 0).getbbox()
    box = (max(0,box[0]-3), max(0,box[1]-3), min(image.width,box[2]+3), min(image.height,box[3]+3))
    crop = image.crop(box)
    padded = Image.new('RGBA', (crop.width+24, crop.height+24))
    padded.alpha_composite(crop,(12,12))
    # Generated solid cloth/hair interiors have alpha 252-254; normalize
    # those opaque surfaces so split overlaps do not make a dark stripe.
    padded.putalpha(padded.getchannel('A').point(lambda a:255 if a>240 else a))
    padded.save(OUT/(name+'.png'))
    return {'source_bbox':list(box),'padding':12,'size':list(padded.size)}


def extract():
    OUT.mkdir(exist_ok=True)
    image=Image.open(SRC/'parts_sheet.png').convert('RGBA')
    w,h=image.size
    remaining=bytearray(image.getchannel('A').point(lambda a:255 if a>24 else 0).tobytes())
    groups=[]
    for i in range(len(remaining)):
        if not remaining[i]: continue
        remaining[i]=0;queue=deque([i]);pixels=[]
        while queue:
            k=queue.popleft();pixels.append(k);x,y=k%w,k//w
            for n in (k-1 if x else -1,k+1 if x<w-1 else -1,k-w,k+w):
                if 0<=n<len(remaining) and remaining[n]:
                    remaining[n]=0;queue.append(n)
        if len(pixels)>2000:groups.append(pixels)
    if len(groups)!=4:raise ValueError(f'Expected four connected components; got {len(groups)}')
    result={}
    # Identify by location, not traversal order or the generator's cell sizes.
    for pixels in groups:
        cx=sum(k%w for k in pixels)/len(pixels);cy=sum(k//w for k in pixels)/len(pixels)
        name=('head_sit' if cx<w*.60 else 'arm_near_pen') if cy<h*.60 else ('book_lap' if cx<w*.60 else 'arm_far')
        assert name not in result
        raw=bytearray(w*h)
        for k in pixels:raw[k]=255
        mask=Image.frombytes('L',(w,h),bytes(raw)).filter(ImageFilter.MaxFilter(5))
        result[name]=save_part(image,name,mask)
    result['body_sit']=save_part(Image.open(SRC/'body_sit.png').convert('RGBA'),'body_sit')
    result['whale_cushion']=save_part(Image.open(ROOT/'assets/art/whale_cushion_v1/whale_cushion.png').convert('RGBA'),'whale_cushion')
    # Split the already-extracted head at the neck; both layers follow ONE
    # control so the shared hair boundary cannot drift apart.
    combined=Image.open(OUT/'head_sit.png').convert('RGBA')
    cut=548-result['head_sit']['source_bbox'][1]+12
    # Overlap exceeds the Lanczos filter footprint at the delivery scale.
    for name,rect in [('head_front',(0,0,combined.width,cut+8)),
                      ('hair_back',(0,cut-8,combined.width,combined.height))]:
        mask=Image.new('L',combined.size)
        ImageDraw.Draw(mask).rectangle((rect[0],rect[1],rect[2]-1,rect[3]-1),fill=255)
        layer=combined.copy();layer.putalpha(ImageChops.multiply(layer.getchannel('A'),mask))
        layer.save(OUT/(name+'.png'))
        result[name]=dict(result['head_sit'])
    return result


def assemble(parts):
    # Pivots are coordinates in the original source images. Convert them to
    # padded cutout coordinates here so extraction never loses registration.
    specs=[
        ('whale_cushion',(0,0),(0,-35),1,0),
        ('hair_back',(400,540),(735,555),.85,0),
        ('body_sit',(0,0),(0,0),1,0),
        ('head_front',(400,540),(735,555),.85,0),
        ('book_lap',(45,935),(745,785),.50,0),
        ('arm_far',(910,875),(850,620),.60,10),
        ('arm_near_pen',(900,263),(650,615),.55,0),
    ]
    canvas=Image.new('RGBA',(1280,1280));layers=[]
    for name,pivot,position,scale,angle in specs:
        box=parts[name]['source_bbox']
        local=[pivot[0]-box[0]+12,pivot[1]-box[1]+12]
        image=Image.open(OUT/(name+'.png')).convert('RGBA')
        tile,at=positioned(image,local,position,scale,angle)
        canvas.alpha_composite(tile,at)
        layers.append({'name':name,'pivot':local,'position':list(position),'scale':scale,'angle':angle})
    canvas.save(OUT/'assembled.png')
    for bg,name in [('#e6edf5','assembled-light.jpg'),('#252b39','assembled-dark.jpg')]:
        preview=Image.new('RGBA',canvas.size,bg);preview.alpha_composite(canvas)
        preview.convert('RGB').save(OUT/name,quality=94)
    manifest={'canvas':[1280,1280],'coordinates':'top-left origin, +y down, angles clockwise; uniform scales',
              'parts':parts,'draw_order_back_to_front':layers,'status':'static assembly; animation not implemented'}
    (OUT/'assembly.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    # Minimal editor-import setup. The root uses the preview's top-left
    # origin, with Spine y/rotation signs inverted. No animation is claimed.
    setup={'skeleton':{'spine':'4.2.43','x':0,'y':-1280,'width':1280,'height':1280,'images':'./'},
           'bones':[{'name':'root'},{'name':'sit_body','parent':'root'}],
           'slots':[],'skins':[{'name':'default','attachments':{}}],'animations':{}}
    bones={'root','sit_body'}
    for layer in layers:
        name=layer['name'];bone='sit_head' if name in ('head_front','hair_back') else name
        if name=='body_sit':bone='sit_body'
        if bone not in bones:
            setup['bones'].append({'name':bone,'parent':'root' if name=='whale_cushion' else 'sit_body',
                                  'x':layer['position'][0],'y':-layer['position'][1],
                                  'rotation':-layer['angle']})
            bones.add(bone)
        setup['slots'].append({'name':name,'bone':bone,'attachment':name})
        w,h=parts[name]['size'];px,py=layer['pivot'];scale=layer['scale']
        setup['skins'][0]['attachments'][name]={name:{'type':'region','path':name,
            'x':(w/2-px)*scale,'y':-(h/2-py)*scale,'width':w*scale,'height':h*scale}}
    (OUT/'seated_setup.spine-json').write_text(json.dumps(setup,indent=2),encoding='utf-8')
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',18)
    sheet=Image.new('RGB',(1200,1080),'#e6edf5');d=ImageDraw.Draw(sheet)
    for i,name in enumerate(['whale_cushion','body_sit','hair_back','head_front','book_lap','arm_far','arm_near_pen']):
        im=Image.open(OUT/(name+'.png')).convert('RGBA');im.thumbnail((380,300),Image.Resampling.LANCZOS)
        x,y=i%3*400,i//3*360
        sheet.paste(im,(x+(400-im.width)//2,y+(310-im.height)//2),im)
        d.text((x+15,y+325),name,font=font,fill='#233d61')
    sheet.save(OUT/'parts-overview.jpg',quality=94)
    # Annotated assembly guide; approximate anatomical pivots must be checked
    # against the final meshes before animation. Nib is fixed to writing hand.
    anchors={'neck':[735,555],'shoulder_near':[650,615],'elbow_near':[663,732],
             'wrist_near':[730,792],'pen_tip':[817,858],
             'shoulder_far':[850,620],'elbow_far':[878,709],'wrist_far':[935,779],
             'support_fingers':[985,810],'hip':[780,950],'ground':[1050,1214]}
    diagram=Image.open(OUT/'assembled-light.jpg');draw=ImageDraw.Draw(diagram)
    for name,(x,y) in anchors.items():
        draw.ellipse((x-5,y-5,x+5,y+5),fill='#e84b49',outline='white',width=2)
        draw.text((x+8,y-20),name,font=font,fill='#b52027',stroke_width=2,stroke_fill='white')
    diagram.save(OUT/'anchors.jpg',quality=94)
    (OUT/'anchors.json').write_text(json.dumps({'coordinates':'same screen coordinates as assembly.json',
        'status':'static anatomical guides, NOT animated IK solution','points':anchors},indent=2),encoding='utf-8')
    print(json.dumps(parts))


if __name__=='__main__':assemble(extract())
