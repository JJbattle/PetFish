# -*- coding: utf-8 -*-
"""Cut the flat background out of the pet artwork.

Usage:
    python preprocess.py <source image> <output png> [--tolerance 60] [--pad 4]

The source is a character on a flat light-grey backdrop (possibly with a
watermark / caption text).  We flood-fill the backdrop from the border, keep
only the largest connected foreground blob (drops captions and watermarks that
are not attached to the character), feather the edge by one pixel and crop to
the bounding box.

Pure Pillow + stdlib, no numpy required.
"""

import os
import sys
from collections import deque

from PIL import Image, ImageFilter


def border_background(px, w, h):
    """Median colour of the image border."""
    samples = []
    for x in range(w):
        samples.append(px[x, 0][:3])
        samples.append(px[x, h - 1][:3])
    for y in range(h):
        samples.append(px[0, y][:3])
        samples.append(px[w - 1, y][:3])
    if not samples:
        return (255, 255, 255)
    return tuple(
        sorted(c[i] for c in samples)[len(samples) // 2] for i in range(3)
    )


def flood_background(px, w, h, bg, tolerance):
    """Mark pixels reachable from the border whose colour is close to bg."""
    limit = tolerance
    marked = bytearray(w * h)
    queue = deque()

    def near_bg(x, y):
        c = px[x, y]
        return abs(c[0] - bg[0]) + abs(c[1] - bg[1]) + abs(c[2] - bg[2]) <= limit

    def push(x, y):
        idx = y * w + x
        if marked[idx]:
            return
        if near_bg(x, y):
            marked[idx] = 1
            queue.append(idx)

    for x in range(w):
        push(x, 0)
        push(x, h - 1)
    for y in range(h):
        push(0, y)
        push(w - 1, y)

    while queue:
        idx = queue.popleft()
        x, y = idx % w, idx // w
        if x > 0:
            push(x - 1, y)
        if x + 1 < w:
            push(x + 1, y)
        if y > 0:
            push(x, y - 1)
        if y + 1 < h:
            push(x, y + 1)
    return marked


def largest_component(marked, w, h):
    """Return a bytearray of the biggest 4-connected non-background blob."""
    seen = bytearray(w * h)
    best = bytearray(w * h)
    best_size = 0

    for start in range(w * h):
        if marked[start] or seen[start]:
            continue
        seen[start] = 1
        queue = deque([start])
        blob = []
        while queue:
            idx = queue.popleft()
            blob.append(idx)
            x, y = idx % w, idx // w
            for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
                if 0 <= nx < w and 0 <= ny < h:
                    nidx = ny * w + nx
                    if not marked[nidx] and not seen[nidx]:
                        seen[nidx] = 1
                        queue.append(nidx)
        if len(blob) > best_size:
            best_size = len(blob)
            keep = bytearray(w * h)
            for idx in blob:
                keep[idx] = 255
            best = keep
    return best, best_size


def main(argv):
    if len(argv) < 3:
        print(__doc__)
        return 2

    src, dst = argv[1], argv[2]
    tolerance = 60
    pad = 4
    rest = argv[3:]
    for i, arg in enumerate(rest):
        if arg == "--tolerance" and i + 1 < len(rest):
            tolerance = int(rest[i + 1])
        elif arg == "--pad" and i + 1 < len(rest):
            pad = int(rest[i + 1])

    if not os.path.isfile(src):
        print("source not found:", src)
        return 1

    img = Image.open(src).convert("RGBA")
    w, h = img.size
    px = img.load()
    bg = border_background(px, w, h)
    print("size: %dx%d  border colour: #%02X%02X%02X" % ((w, h) + bg))

    bg_mask = flood_background(px, w, h, bg, tolerance)
    fg_mask, fg_size = largest_component(bg_mask, w, h)
    ratio = fg_size / float(w * h)
    print("background px: %d  largest blob: %d (%.1f%%)" % (
        sum(bg_mask), fg_size, ratio * 100.0
    ))
    if ratio < 0.05:
        print("WARNING: foreground blob is tiny - check the background colour/tolerance")

    alpha = Image.frombytes("L", (w, h), bytes(fg_mask))
    alpha = alpha.filter(ImageFilter.GaussianBlur(0.8))

    out = img.copy()
    out.putalpha(alpha)

    # Kill colour fringes in fully transparent area.
    transparent = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out = Image.composite(out, transparent, alpha.point(lambda v: 255 if v > 0 else 0))

    bbox = out.getbbox()
    if bbox is None:
        print("ERROR: nothing left after background removal")
        return 1
    left, top, right, bottom = bbox
    left = max(0, left - pad)
    top = max(0, top - pad)
    right = min(w, right + pad)
    bottom = min(h, bottom + pad)
    out = out.crop((left, top, right, bottom))

    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    out.save(dst, "PNG")
    print("wrote %s  (%dx%d)" % (dst, out.size[0], out.size[1]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
