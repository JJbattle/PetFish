"""Determine the spine-godot region-attachment coordinate convention.

Renders one region of known size/offset/color through the real Spine runtime and
reports where its corners land, so the rest rig can be authored against the
actual convention instead of a guess.

Reuses the already-imported `rest_preview_proj` (which has the Spine importer
registered) to avoid the fresh-project first-import crash.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'tools/_debug/rest_preview_proj'
ADDON_SRC = ROOT / 'game/addons/spine-godot/bin'
GODOT = r'D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64.exe'


def run(command, log, timeout):
    environment = os.environ.copy()
    environment['APPDATA'] = str(PROJECT / 'userdata')
    Path(environment['APPDATA']).mkdir(parents=True, exist_ok=True)
    (Path(environment['APPDATA']) / '.gdignore').touch()
    with log.open('w', encoding='utf-8') as stream:
        child = subprocess.Popen(command, cwd=ROOT, stdout=stream,
                                 stderr=subprocess.STDOUT, env=environment,
                                 creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            code = child.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill', '/PID', str(child.pid), '/T', '/F'],
                           capture_output=True, timeout=10)
            raise RuntimeError('probe timed out')
    output = log.read_text(encoding='utf-8', errors='replace')
    if code or 'SCRIPT ERROR:' in output or 'Parse Error:' in output:
        raise RuntimeError('probe failed exit %s: %s' % (code, output[-500:]))
    return output


def main():
    PROJECT.mkdir(parents=True, exist_ok=True)
    addon = PROJECT / 'addons/spine-godot/bin'
    (addon / 'windows').mkdir(parents=True, exist_ok=True)
    shutil.copy2(ADDON_SRC / 'windows/libspine_godot.windows.editor.x86_64.dll', addon / 'windows')
    shutil.copy2(ADDON_SRC / 'spine_godot_extension.gdextension', addon)

    # test image: 100x100, red TL 10x10, blue BL 10x10, rest green
    img = Image.new('RGBA', (100, 100), (0, 200, 0, 255))
    for y in range(10):
        for x in range(10):
            img.putpixel((x, y), (255, 0, 0, 255))        # top-left red
            img.putpixel((x, 99 - y), (0, 0, 255, 255))   # bottom-left blue
    assets = PROJECT / 'assets'
    assets.mkdir(exist_ok=True)
    img.save(assets / 'probe.png')

    dx, dy = 40.0, 30.0
    (assets / 'probe.atlas').write_text(
        'probe.png\nsize: 100,100\nformat: RGBA8888\nfilter: Linear,Linear\nrepeat: none\n'
        'probe\n  rotate: false\n  xy: 0, 0\n  size: 100, 100\n  orig: 100, 100\n'
        '  offset: 0, 0\n  index: -1\n', encoding='utf-8')
    skeleton = {
        'skeleton': {'spine': '4.2.43', 'x': 0, 'y': 0, 'width': 100, 'height': 100,
                     'images': './', 'audio': ''},
        'bones': [{'name': 'root'}, {'name': 'b', 'parent': 'root', 'x': 0, 'y': 0}],
        'slots': [{'name': 's', 'bone': 'b', 'attachment': 'probe'}],
        'skins': [{'name': 'default', 'attachments': {'s': {'probe': {
            'type': 'region', 'path': 'probe',
            'x': dx, 'y': dy, 'width': 100, 'height': 100}}}}],
        'animations': {},
    }
    (assets / 'probe.spine-json').write_text(json.dumps(skeleton), encoding='utf-8')

    (PROJECT / 'project.godot').write_text(
        'config_version=5\n[application]\nconfig/name="probe"\nrun/main_scene="res://probe.tscn"\n'
        '[display]\nwindow/size/viewport_width=500\nwindow/size/viewport_height=500\n'
        'window/size/always_on_top=false\nwindow/size/borderless=false\nwindow/size/transparent=false\n'
        '[rendering]\nrenderer/rendering_method="gl_compatibility"\n', encoding='utf-8')
    (PROJECT / 'probe.gd').write_text('''extends Node
func _ready():
    get_window().always_on_top = false
    var vp := SubViewport.new()
    vp.size = Vector2i(500, 500)
    vp.transparent_bg = true
    vp.render_target_update_mode = SubViewport.UPDATE_ALWAYS
    add_child(vp)
    var data := SpineSkeletonDataResource.new()
    data.skeleton_file_res = load("res://assets/probe.spine-json")
    data.atlas_res = load("res://assets/probe.atlas")
    data.update_skeleton_data()
    var rig := SpineSprite.new()
    rig.skeleton_data_res = data
    rig.update_mode = 2
    rig.position = Vector2(250, 250)
    vp.add_child(rig)
    await get_tree().process_frame
    rig.get_skeleton().set_to_setup_pose()
    rig.update_skeleton(0.0)
    await get_tree().process_frame
    var bone := rig.get_skeleton().find_bone("b")
    print("BONE_WORLD ", bone.get_world_x(), ",", bone.get_world_y())
    RenderingServer.force_draw(false)
    var err := vp.get_texture().get_image().save_png("res://out.png")
    print("SAVED ", err)
    get_tree().quit()
''', encoding='utf-8')
    (PROJECT / 'probe.tscn').write_text('[gd_scene load_steps=2 format=3]\n[ext_resource type="Script" path="res://probe.gd" id="1"]\n[node name="P" type="Node"]\nscript = ExtResource("1")\n', encoding='utf-8')

    run([GODOT, '--headless', '--path', str(PROJECT), '--editor', '--import', '--quit'],
        PROJECT / 'import.log', 60)
    run([GODOT, '--path', str(PROJECT), '--rendering-driver', 'opengl3'],
        PROJECT / 'render.log', 60)

    out = Image.open(PROJECT / 'out.png').convert('RGBA')
    px = out.load()
    red = blue = None
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, a = px[x, y]
            if a < 200:
                continue
            if r > 200 and g < 100 and b < 100:
                red = (min(red[0], x) if red else x, min(red[1], y) if red else y,
                       max(red[2], x) if red else x, max(red[3], y) if red else y)
            elif b > 200 and r < 100 and g < 100:
                blue = (min(blue[0], x) if blue else x, min(blue[1], y) if blue else y,
                        max(blue[2], x) if blue else x, max(blue[3], y) if blue else y)
    print('region offset (x=%s,y=%s) size 100x100 at bone (250,250):' % (dx, dy))
    print('  RED   (image top-left)  bbox:', red)
    print('  BLUE  (image bottom-left) bbox:', blue)


if __name__ == '__main__':
    main()
