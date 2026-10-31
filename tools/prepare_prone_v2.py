"""Register prone reading attachments to their source pixels. No game writes."""
import json
import math
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
ART = ROOT / 'assets/art/prone_reading_v2'
KIT = ART / 'kit'
# Atlas space, y down. Stop the moving portions well above their cut lines.
CUTS = {
    'fluke': [(968, 129), (1270, 129), (1270, 348), (968, 348)],
    'shoe_far': [(1274, 254), (1405, 254), (1405, 320), (1360, 397), (1240, 397), (1258, 333)],
    'shoe_near': [(1430, 310), (1535, 309), (1535, 465), (1350, 465), (1370, 399)],
}
CONTROLS = {'reading': (514, 653), 'fluke': (1065, 372),
            'shoe_far': (1286, 418), 'shoe_near': (1380, 497)}


def mesh(name, box, bone_index):
    left, top, right, bottom = box
    w, h = right-left, bottom-top
    nx, ny = math.ceil(w/48), math.ceil(h/48)
    # Spine stores outline vertices first; keep one ring then the interior.
    ring = ([(i, 0) for i in range(nx+1)] + [(nx, j) for j in range(1, ny+1)]
            + [(i, ny) for i in reversed(range(nx))] + [(0, j) for j in reversed(range(1, ny))])
    grid = ring + [(i, j) for j in range(1, ny) for i in range(1, nx)]
    indices = {xy: i for i, xy in enumerate(grid)}
    uvs, vertices, triangles = [], [], []
    px, py = CONTROLS[name]
    for i, j in grid:
        u, v = i/nx, j/ny
        x, y = left+w*u, top+h*v
        if name == 'reading':
            weight = max(0, min(1, (660-y)/145, (900-x)/180))
        else:
            weight = max(0, min(1, (bottom-50-y)/95))
        weight = weight*weight*(3-2*weight)
        uvs.extend([u, v])
        # root is at (0, 0); child pivots above are in canvas coordinates.
        if weight == 0:
            vertices.extend([1, 0, x, -y, 1])
        elif weight == 1:
            vertices.extend([1, bone_index, x-px, py-y, 1])
        else:
            vertices.extend([2, 0, x, -y, 1-weight, bone_index, x-px, py-y, weight])
    for j in range(ny):
        for i in range(nx):
            a, b, c, d = [indices[p] for p in [(i,j),(i+1,j),(i+1,j+1),(i,j+1)]]
            triangles.extend([a,b,c,a,c,d])
    return dict(type='mesh', path=name, uvs=uvs, triangles=triangles,
                vertices=vertices, hull=len(ring), width=w, height=h)


def build():
    master = Image.open(ART/'master.png').convert('RGBA')
    assert master.size == (1536, 1024)
    base = master.copy()
    pieces = {}
    for name, polygon in CUTS.items():
        mask = Image.new('L', master.size)
        ImageDraw.Draw(mask).polygon(polygon, fill=255)
        cut = base.copy()
        cut.putalpha(ImageChops.multiply(base.getchannel('A'), mask))
        base.paste((0,0,0,0), (0,0,*master.size), mask)
        pieces[name] = cut
    pieces['reading'] = base
    layers = ['reading', *CUTS]
    setup = {'skeleton': {'spine':'4.2.43','images':'./','width':1536,'height':1024,'y':-1024},
             'bones':[{'name':'root'}], 'slots':[],
             'skins':[{'name':'default','attachments':{}}], 'animations':{}}
    out = Image.new('RGBA', master.size)
    manifest = {}
    for i, name in enumerate(layers, start=1):
        piece = pieces[name]
        l,t,r,b = piece.getchannel('A').getbbox()
        box = (l-3,t-3,r+3,b+3)
        cropped = piece.crop(box)
        cropped.save(KIT/(name+'.png'))
        out.alpha_composite(cropped, box[:2])
        x,y = CONTROLS[name]
        setup['bones'].append(dict(name=name, parent='root', x=x, y=-y))
        setup['slots'].append(dict(name=name, bone='root', attachment=name))
        setup['skins'][0]['attachments'][name] = {name:mesh(name,box,i)}
        manifest[name] = {'top_left':box[:2], 'size':cropped.size,'control':[x,y]}
    assert ImageChops.difference(master.getchannel('A'),out.getchannel('A')).getbbox() is None
    for bg in ['#edf0f5','#242735']:
        a, b = [Image.new('RGBA',master.size,bg) for _ in range(2)]
        a.alpha_composite(master)
        b.alpha_composite(out)
        assert not ImageChops.difference(a.convert('RGB'),b.convert('RGB')).getbbox()
    out.save(KIT/'assembled.png')
    small = b.convert('RGB')
    small.thumbnail((760,520),Image.Resampling.LANCZOS)
    small.save(KIT/'preview.jpg', quality=95)
    (KIT/'assembly.json').write_text(json.dumps(manifest,indent=2), encoding='utf-8')
    (KIT/'prone_v2.json').write_text(json.dumps(setup,separators=(',',':')),encoding='utf-8')
    archive = ROOT/'docs/prone-reading-v2-kit.zip'
    with ZipFile(archive,'w',ZIP_DEFLATED) as z:
        for path in sorted(KIT.iterdir()):
            if path.is_file():
                z.write(path,path.name)
    with ZipFile(archive) as z:
        assert z.testzip() is None
    print(manifest)


if __name__ == '__main__':
    build()
