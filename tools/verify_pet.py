"""Run production-script regressions in the isolated preview project.

First run preview_pose.py --all --silhouette to prepare the project/assets.
No production window, session directory or reminder profile is opened.
"""
from pathlib import Path
import argparse
import shutil
from preview_pose import PROJECT, ROOT, run


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--godot', default=r'D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64.exe')
    args = parser.parse_args()
    if not (PROJECT / 'project.godot').exists():
        parser.error('Run tools/preview_pose.py first')
    scripts = PROJECT / 'scripts'
    scripts.mkdir(exist_ok=True)
    for source in (ROOT / 'game/scripts').glob('*.gd'):
        shutil.copy2(source, scripts / source.name)
    assets = PROJECT / 'assets/pet_spine'
    assets.mkdir(exist_ok=True)
    for name in ('pet.png', 'pet.atlas', 'pet.spine-json', 'pet_silhouette.png'):
        shutil.copy2(ROOT / 'game/assets/pet_spine' / name, assets / name)
    shutil.copy2(ROOT / 'tools/runtime_check.gd', PROJECT / 'runtime_check.gd')
    (PROJECT / 'runtime_check.tscn').write_text('''[gd_scene load_steps=2 format=3]
[ext_resource type="Script" path="res://runtime_check.gd" id="1"]
[node name="Checks" type="Node"]
script = ExtResource("1")
''', encoding='utf-8')
    run([args.godot, '--headless', '--path', str(PROJECT), '--editor', '--import', '--quit'],
        PROJECT / 'verify-import.log', 45)
    run([args.godot, '--headless', '--path', str(PROJECT), 'res://runtime_check.tscn'],
        PROJECT / 'verify-runtime.log', 45)
    print((PROJECT / 'verify-runtime.log').read_text(encoding='utf-8', errors='replace'))


if __name__ == '__main__':
    main()
