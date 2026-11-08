"""Register the compact prone-reading sprite using its own painted landmarks."""
from prepare_prone_v2 import ROOT, build
from PIL import Image
import shutil


def add_whale(kit, figure, setup, manifest):
    # Use the seated prop at the same apparent size relative to the head.
    source = ROOT / 'assets/art/whale_seated_work_v2/kit/whale_cushion.png'
    shutil.copyfile(source, kit/'whale_cushion.png')
    width, height = Image.open(source).size
    scale = .65 * 528 / 379
    w, h = width * scale, height * scale
    left, top, shift = 12, 384, 354
    setup['bones'][0]['x'] = shift
    name = 'whale_cushion'
    setup['slots'].insert(0, dict(name=name, bone='root', attachment=name))
    setup['skins'][0]['attachments'][name] = {name: dict(type='region', path=name,
        width=w, height=h, x=left-shift+w/2, y=-top-h/2)}
    manifest['scene'] = dict(character_offset=[shift,0], cushion_top_left=[left,top],
                             cushion_scale=scale, draw_order='cushion behind all character slots')
    out = Image.new('RGBA',figure.size)
    with Image.open(source) as whale:
        out.alpha_composite(whale.resize((round(w),round(h)),Image.Resampling.LANCZOS),(left,top))
    out.alpha_composite(figure,(shift,0))
    return out


if __name__ == '__main__':
    # Only the distal portions are animated. The roots remain on the core.
    cuts = {
        'fluke': [(758, 110), (984, 110), (984, 266), (778, 266), (758, 236)],
        'shoe_far': [(974, 275), (1010, 273), (1010, 328), (981, 348),
                     (920, 327), (922, 312), (948, 297)],
        'shoe_near': [(1011, 297), (1125, 297), (1125, 393),
                      (1086, 399), (1008, 367)],
    }
    controls = {'reading': (510, 677), 'fluke': (842, 315),
                'shoe_far': (948, 352), 'shoe_near': (1046, 409)}
    build(ROOT / 'assets/art/prone_reading_v3', cuts, controls,
          head_fade=(730, 680), version='v3', master_name='character_without_cushion.png',
          furnish=add_whale)
