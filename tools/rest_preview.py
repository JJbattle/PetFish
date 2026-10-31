"""Render the standalone rest rig in an isolated, non-overlay Godot project.

Mirrors tools/preview_pose.py: only the child this invocation launches is killed
on timeout, and the production project/editor/session data are never loaded.

After rendering it also diffs the setup pose against the manifest's own
`assembled.png`, so a wrong Spine coordinate convention is caught numerically
rather than by eye.
"""
from pathlib import Path
import argparse
import json
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'tools/_debug/rest_preview_proj'
REST_SPINE = ROOT / 'tools/_debug/rest_spine'
REFERENCE = ROOT / 'assets/art/rest_whale_v1/assembled.png'

CANVAS = (1200, 850)


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
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--godot', default=r'D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64.exe')
    parser.add_argument('--scale', type=float, default=1.0,
                        help='rig render scale (canvas pixels -> screen pixels)')
    parser.add_argument('--poses', default='rest_whale_loop:0.0')
    parser.add_argument('--out', default='tools/_debug/rest_preview')
    parser.add_argument('--no-diff', action='store_true')
    args = parser.parse_args()

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
    for name in ('rest.png', 'rest.atlas', 'rest.spine-json'):
        shutil.copy2(REST_SPINE / name, assets / name)

    (PROJECT / 'project.godot').write_text('''config_version=5
[application]
config/name="FishPet rest preview"
run/main_scene="res://preview.tscn"
[display]
window/size/viewport_width=1200
window/size/viewport_height=850
window/size/always_on_top=false
window/size/borderless=false
window/size/transparent=false
[rendering]
renderer/rendering_method="gl_compatibility"
''', encoding='utf-8')
    shutil.copy2(ROOT / 'tools/rest_preview.gd', PROJECT / 'preview.gd')
    (PROJECT / 'preview.tscn').write_text('''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://preview.gd" id="1"]
[node name="Preview" type="Node"]
script = ExtResource("1")
''', encoding='utf-8')

    out = (ROOT / args.out).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / '.gdignore').touch()

    run([args.godot, '--headless', '--path', str(PROJECT), '--editor', '--import', '--quit'],
        PROJECT / 'import.log', 45)

    (PROJECT / 'request.json').write_text(json.dumps({
        'poses': args.poses,
        'out': str(out),
        'scale': args.scale,
        'vp': [int(CANVAS[0] * args.scale), int(CANVAS[1] * args.scale)],
    }), encoding='utf-8')
    run([args.godot, '--path', str(PROJECT), '--rendering-driver', 'opengl3', '--max-fps', '30'],
        PROJECT / 'render.log', 55)

    if not args.no_diff:
        from PIL import Image, ImageChops
        ref = Image.open(REFERENCE).convert('RGBA')
        first = args.poses.split(',')[0].split(':')[0]
        shot = out / ('%s_%.3f.png' % (first, 0.0))
        if shot.exists():
            got = Image.open(shot).convert('RGBA')
            if got.size != ref.size:
                print('DIFF: size mismatch ref=%s got=%s' % (ref.size, got.size))
            else:
                a = ref.getchannel('A').point(lambda v: 255 if v > 25 else 0)
                b = got.getchannel('A').point(lambda v: 255 if v > 25 else 0)
                overlap = ImageChops.multiply(a, b).getbbox()
                print('DIFF: ref bbox', ref.getbbox(), 'got bbox', got.getbbox(),
                      'alpha overlap', overlap)
    print('CAPTURES', out)


if __name__ == '__main__':
    main()
