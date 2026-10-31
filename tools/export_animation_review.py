"""Package real Godot captures into a portable, offline animation review."""
from pathlib import Path
import argparse
import json
import math
import subprocess
import sys
from PIL import Image, ImageDraw, ImageFont, ImageChops, ImageFilter

ROOT = Path(__file__).resolve().parents[1]
CAPTURES = ROOT / 'tools/_debug/codex_preview/review_motion_v4'
OUT = ROOT / 'docs/animation-review-20261025-v4'
FPS = 12
CHAINS = {
    'idle': ('待机 · 左右顾盼', ['idle']),
    'slack': ('摸鱼 · 抱鲸鱼轻抚', ['slack_in', 'slack', 'slack_out']),
    'present': ('展示一 · 右键菜单', ['present_in', 'present', 'present_out']),
    'present2': ('展示二 · 提醒设置', ['present2_in', 'present2', 'present2_out']),
    'drink': ('喝水 · 双手捧杯仰头', ['drink_in', 'drink_sip', 'drink_sip2', 'drink_out']),
    'working': ('工作 · 抱本写字', ['working_in', 'working', 'working_out']),
    'reminders': ('提醒 · 持续跳跃、双手挥动', ['hop_sit', 'hop_sit', 'hop_sit', 'hop_sit']),
}


def times(value):
    if isinstance(value, dict):
        yield value.get('time', 0)
        for child in value.values():
            yield from times(child)
    elif isinstance(value, list):
        for child in value:
            yield from times(child)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--package-only', action='store_true')
    args = parser.parse_args()
    document = json.loads((ROOT / 'game/assets/pet_spine/pet.spine-json').read_text())
    sequences = {}
    for name, (_, clips) in CHAINS.items():
        samples = []
        for clip in clips:
            end = max(times(document['animations'][clip]))
            samples += [(clip, round(i / FPS, 3)) for i in range(math.ceil(end * FPS))]
        sequences[name] = samples
    if not args.package_only:
        specs = dict.fromkeys(f'{clip}:{t}' for samples in sequences.values() for clip, t in samples)
        subprocess.run([sys.executable, str(ROOT / 'tools/preview_pose.py'), '--out',
                        'review_motion_v4', '--poses', ','.join(specs)], cwd=ROOT, check=True)
    OUT.mkdir(parents=True, exist_ok=True)
    # Dense review frames may catch arc extrema between the coarse all-clip
    # samples. Expand (never shrink) the shipped union to include them.
    silhouette_path = ROOT / 'game/assets/pet_spine/pet_silhouette.png'
    union = Image.new('L', (1024, 1024))
    for path in CAPTURES.glob('*.png'):
        with Image.open(path) as frame:
            union = ImageChops.lighter(union, frame.getchannel('A'))
    union = union.point(lambda a: 255 if a > 25 else 0).filter(ImageFilter.MaxFilter(21))
    with Image.open(silhouette_path) as previous:
        union = ImageChops.lighter(union, previous.getchannel('A'))
    silhouette = Image.new('RGBA', union.size, 'white')
    silhouette.putalpha(union)
    silhouette.save(silhouette_path)
    for name, samples in sequences.items():
        frames = []
        for clip, t in samples:
            with Image.open(CAPTURES / f'{clip}_{t:.3f}.png') as image:
                frames.append(image.convert('RGBA').resize((424, 424), Image.Resampling.LANCZOS))
        frames[0].save(OUT / f'{name}.webp', save_all=True, append_images=frames[1:],
                       duration=round(1000 / FPS), loop=0, quality=88, method=4)
        if name in ('slack', 'drink'):
            closeups = []
            for clip, t in samples:
                with Image.open(CAPTURES / f'{clip}_{t:.3f}.png') as image:
                    closeups.append(image.convert('RGBA').crop((300, 330, 760, 790))
                                    .resize((512, 512), Image.Resampling.LANCZOS))
            closeups[0].save(OUT / f'{name}-detail.webp', save_all=True,
                            append_images=closeups[1:], duration=round(1000 / FPS),
                            loop=0, quality=94, method=4)
    # Static representative poses at consistent scale, not newly generated art.
    selected = [('slack', 1.0), ('present', 1.0), ('present2', 1.0), ('drink_sip', .5), ('working', 1.0)]
    titles = ['从下方托住鲸鱼', '展示一：右键菜单', '展示二：提醒设置', '转臂抬杯、逐口喝', '抱本写字']
    sheet = Image.new('RGB', (1400, 420), '#eef3fb')
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 20)
    for i, ((clip, t), title) in enumerate(zip(selected, titles)):
        with Image.open(CAPTURES / f'{clip}_{t:.3f}.png') as source:
            sprite = source.crop((145, 80, 855, 980)).resize((268, 340), Image.Resampling.LANCZOS)
        sheet.paste(sprite, (i * 280 + 6, 15), sprite)
        draw.text((i * 280 + 30, 375), title, font=font, fill='#22395b')
    sheet.save(OUT / 'five-poses.png')
    cards = '\n'.join(f'<article><h2>{title}</h2><img src="{name}.webp" alt="{title}"></article>'
                      for name, (title, _) in CHAINS.items())
    html = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>FishPet 动画验收</title><style>
body{margin:32px;background:#edf2fa;color:#203453;font:16px/1.65 system-ui,"Microsoft YaHei",sans-serif}
h1{font-size:26px}h2{font-size:16px}p{max-width:900px}button{padding:8px 16px;margin:0 8px 12px 0;cursor:pointer}
main{display:flex;flex-wrap:wrap;gap:20px}article{background:white;border:1px solid #d6e0ed;border-radius:16px;padding:18px}
img{width:212px;height:212px;object-fit:contain;display:block}body.large img{width:424px;height:424px}
small{color:#516784}a{color:#2655a5}</style>
<h1>FishPet 动画验收 · 第 4 版 · 2026-10-25</h1>
<p>本版补画喝水原图：去掉两层袖口之间错误的裸露皮肤和多余花边，改为连续深蓝长袖，每只手腕只保留一个白色袖口。保留第 3 版的连续袖子网格与摸鱼修正。</p>
<p><a href="drink-sleeve-before-after.png">查看实际骨架同一时刻的袖子修改前后对照</a></p>
<main><article><h2>摸鱼 · 手腕与袖口放大</h2><img style="width:360px;height:360px" src="slack-detail.webp" alt="摸鱼手臂连续动作放大"></article>
<article><h2>喝水 · 肩、肘接缝放大</h2><img style="width:360px;height:360px" src="drink-detail.webp" alt="喝水袖子连续动作放大"></article></main>
<p>以下为 Godot / Spine 实际骨架渲染，包含入场、保持和退场。默认角色基准高度 170 px；可放大检查手指、袖口与杯沿。动画按 12 帧/秒抽样展示，游戏运行速度不受影响。</p>
<button onclick="document.body.classList.remove('large')">170 px 基准</button>
<button onclick="document.body.classList.add('large')">340 px 放大检查</button>
<main>''' + cards + '''</main><p><small>提醒持续循环跳跃并挥动双手；展示一用于右键菜单、展示二用于提醒设置；喝水靠上臂与前臂旋转，小幅起落表现逐口啜饮；左手托住鲸鱼下沿。普通提醒点气泡停止，打开菜单暂时展示，关闭后继续未处理的提醒。</small></p>
<p><small>这里是实际骨架渲染的动作片段。正面与侧面仍采用视角附件切换，端杯从胸前附近开始；运行时混合与交互另有回归测试。</small></p>
<p><a href="five-poses.png">打开五动作静态对照</a> · <a href="../../ANIMATION_TAKEOVER_20261025.md">改动及验收记录</a></p></html>'''
    (OUT / 'index.html').write_text(html, encoding='utf-8')
    print('REVIEW', OUT, 'frames', sum(len(s) for s in sequences.values()))


if __name__ == '__main__':
    main()
