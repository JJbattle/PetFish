"""Generate the app icon (white whale on an ocean gradient) from the standing
silhouette, and write game/assets/icon.png + icon.ico.

The whale character is white, so a flat white silhouette on a blue rounded square
stays visible on both light and dark taskbars and reads clearly at 16 px.

Usage: python tools/build_icon.py
"""
import os

from PIL import Image, ImageDraw

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SIL = os.path.join(ROOT, 'game', 'assets', 'pet_spine', 'pet_silhouette.png')
OUT_PNG = os.path.join(ROOT, 'game', 'assets', 'icon.png')
OUT_ICO = os.path.join(ROOT, 'game', 'assets', 'icon.ico')

SIZE = 256
# Alpha bounding box of the standing silhouette (see game/scripts/pet.gd).
SIL_BBOX = (122, 57, 871, 1024)


def _rounded_gradient(size: int, top, bottom, radius: int) -> Image.Image:
    grad = Image.new('RGBA', (size, size))
    px = grad.load()
    for y in range(size):
        t = y / (size - 1)
        c = tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)) + (255,)
        for x in range(size):
            px[x, y] = c
    mask = Image.new('L', (size, size), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, size - 1, size - 1], radius=radius, fill=255)
    out = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    out.paste(grad, (0, 0), mask)
    return out


def main() -> None:
    sil = Image.open(SIL).convert('RGBA').crop(SIL_BBOX)
    icon = _rounded_gradient(SIZE, (74, 144, 226), (26, 54, 93), radius=52)

    # Fit the whale to ~72% of the canvas height, centered (nudged up for optics).
    target_h = int(SIZE * 0.72)
    scale = target_h / sil.height
    new_w = max(1, int(sil.width * scale))
    whale = sil.resize((new_w, target_h), Image.LANCZOS)
    x = (SIZE - new_w) // 2
    y = (SIZE - target_h) // 2 + 6
    icon.paste(whale, (x, y), whale)

    icon.save(OUT_PNG)
    icon.save(OUT_ICO, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
    print('wrote', OUT_PNG, 'and', OUT_ICO)


if __name__ == '__main__':
    main()
