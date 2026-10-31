"""Render rig poses in an isolated, non-overlay Godot project.

Only the child launched by this invocation is terminated on timeout.  The
production project, editor, window settings and session data are never loaded.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'tools/_debug/codex_preview'


def run(command, log, timeout):
    environment = os.environ.copy()
    environment['APPDATA'] = str(PROJECT / 'userdata')
    Path(environment['APPDATA']).mkdir(parents=True, exist_ok=True)
    (Path(environment['APPDATA']) / '.gdignore').touch()
    with log.open('w', encoding='utf-8') as stream:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stream,
                                 stderr=subprocess.STDOUT,
                                 env=environment,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                           capture_output=True, timeout=10)
            child.wait(timeout=10)
            raise RuntimeError(f'Preview timed out; owned PID {child.pid} stopped')
    output = log.read_text(encoding='utf-8', errors='replace')
    if code or 'SCRIPT ERROR:' in output or 'Parse Error:' in output:
        raise RuntimeError(f'Preview failed: exit {code}; see {log}')
    print(f'{log.name}: exit {code}')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--godot', default=r'D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64.exe')
    parser.add_argument('--poses', default='idle:0,present:1,present2:1,slack:1,working:1,drink_in:0.6,drink_sip:0.5,drink_out:0.6')
    parser.add_argument('--out', default='current')
    parser.add_argument('--all', action='store_true', help='Sample every animation, including attachment swaps')
    parser.add_argument('--silhouette', action='store_true', help='Write the union to the production rig (requires --all)')
    args = parser.parse_args()
    if args.silhouette and not args.all:
        parser.error('--silhouette requires --all')
    PROJECT.mkdir(parents=True, exist_ok=True)
    addon = PROJECT / 'addons/spine-godot/bin'
    (addon / 'windows').mkdir(parents=True, exist_ok=True)
    for name in ('libspine_godot.windows.editor.x86_64.dll',):
        target = addon / 'windows' / name
        source = ROOT / 'game/addons/spine-godot/bin/windows' / name
        if not target.exists() or target.stat().st_mtime < source.stat().st_mtime:
            shutil.copy2(source, target)
    shutil.copy2(ROOT / 'game/addons/spine-godot/bin/spine_godot_extension.gdextension', addon)
    assets = PROJECT / 'assets'
    assets.mkdir(exist_ok=True)
    for name in ('pet.png', 'pet.atlas', 'pet.spine-json'):
        shutil.copy2(ROOT / 'game/assets/pet_spine' / name, assets / name)
    (PROJECT / 'project.godot').write_text('''config_version=5
[application]
config/name="FishPet isolated pose preview"
run/main_scene="res://preview.tscn"
[display]
window/size/viewport_width=320
window/size/viewport_height=200
window/size/always_on_top=false
window/size/borderless=false
window/size/transparent=false
[rendering]
renderer/rendering_method="gl_compatibility"
''', encoding='utf-8')
    shutil.copy2(ROOT / 'tools/preview_pose.gd', PROJECT / 'preview.gd')
    (PROJECT / 'preview.tscn').write_text('''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://preview.gd" id="1"]
[node name="Preview" type="Node"]
script = ExtResource("1")
''', encoding='utf-8')
    out = (PROJECT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / '.gdignore').touch()
    if args.all:
        animations = json.loads((assets / 'pet.spine-json').read_text(encoding='utf-8'))['animations']
        def times(value):
            if isinstance(value, dict):
                if 'time' in value:
                    yield float(value['time'])
                for child in value.values():
                    yield from times(child)
            elif isinstance(value, list):
                for child in value:
                    yield from times(child)
        specs = []
        for name, animation in animations.items():
            duration = max(times(animation), default=0)
            samples = {round(duration * i / 8, 3) for i in range(9)}
            samples.update(round(t, 3) for t in times(animation))
            for slot in animation.get('slots', {}).values():
                for key in slot.get('attachment', []):
                    t = key.get('time', 0)
                    samples.update((max(0, round(t - .002, 3)), t))
            specs.extend(f'{name}:{t}' for t in sorted(samples))
        args.poses = ','.join(specs)
    run([args.godot, '--headless', '--path', str(PROJECT), '--editor', '--import', '--quit'], PROJECT / 'import.log', 45)
    specs = args.poses.split(',')
    for start in range(0, len(specs), 80):
        batch = ','.join(specs[start:start + 80])
        (PROJECT / 'request.json').write_text(json.dumps({'poses': batch, 'out': str(out)}), encoding='utf-8')
        run([args.godot, '--path', str(PROJECT), '--rendering-driver', 'opengl3', '--max-fps', '30'],
            PROJECT / f'render-{start // 80:02d}.log', 55)
    if args.silhouette:
        from PIL import Image, ImageChops, ImageFilter
        union = Image.new('L', (1024, 1024))
        for spec in args.poses.split(','):
            name, t = spec.split(':')
            with Image.open(out / f'{name}_{float(t):.3f}.png') as frame:
                union = ImageChops.lighter(union, frame.getchannel('A'))
        union = union.point(lambda a: 255 if a > 25 else 0).filter(ImageFilter.MaxFilter(21))
        image = Image.new('RGBA', union.size, 'white')
        image.putalpha(union)
        image.save(ROOT / 'game/assets/pet_spine/pet_silhouette.png')
        print('SILHOUETTE', union.getbbox())
    print('CAPTURES', out)


if __name__ == '__main__':
    main()
