# Repository Guidelines

## Project Structure & Module Organization

FishPet is a Windows habit companion with water/activity reminders, memos, alarms, and optional local Claude Code progress. Follow the latest scope in `项目总纲.md` and `PRODUCT_FRAMEWORK.md`: stabilize the core, add lightweight rewards, then extract reusable character-independent services. AI chat and cloud services are optional future work, not baseline dependencies.

- `game/` contains the Godot 4.7 project and `main.tscn`; `game/scripts/` separates pet UI, session storage, transcript reading, reminders, and settings.
- Root Python scripts handle hooks (`hook.py`), hook installation (`install_hooks.py`), and legacy image preprocessing (`preprocess.py`).
- `assets/art/` holds source artwork; `tools/build_spine.py` generates rig assets in `game/assets/pet_spine/`. The Spine 4.2 extension lives in `game/addons/spine-godot/`.
- `game/tests/` contains logic checks and screenshot scenes. Runtime files in `state/`, `data/`, and `window.json`, plus captures in `tools/_debug/`, are ignored.

## Build, Test, and Development Commands

Run commands from the repository root. Use a Godot 4.7 executable with the Spine extension available; examples assume `godot` is on `PATH`.

```powershell
.\start_fishpet.bat
python tools/build_spine.py
godot --headless --path game --import
godot --headless --path game res://tests/reminders_test.tscn
python tools/preview_pose.py --all --silhouette
python tools/verify_pet.py
```

These launch the overlay, rebuild the rig (requires Pillow), import resources, check reminders, capture all animations/update clipping bounds, and verify runtime transitions. Preview tools accept `--godot PATH`. Adjust the launcher's `GODOT` path and hard-coded `I:/PetFish` paths when relocating.

## Coding Style & Naming Conventions

Follow existing formatting: tabs in GDScript, four spaces in Python. Use `snake_case` for files/functions/variables, `UPPER_SNAKE_CASE` for constants, and leading underscores for internal members. Prefer GDScript type annotations where practical. No formatter or linter configuration is present. Preserve Godot `.uid` companions and edit scene/project settings through the editor when practical.

## Testing Guidelines

For new rest animations, read `SPINE_REST_HANDOFF.md` and the latest requirements in `项目总纲.md` before editing. `assets/art/rest_whale_v1/` is a static asset kit, not an implemented animation. Preserve the revision 4 drinking sleeves and existing reminder/menu behavior. Historical animation reviews do not override these newer requirements.

Tests use custom Godot scenes; no external framework or coverage threshold is configured. Prefer the isolated preview tools above: they disable overlay flags, isolate data, and terminate only their own child on timeout. Inspect PNGs, attachment swaps, and mixed transitions. Rebuild the silhouette after animation edits. Manually check transparency, dragging, and click-through behavior. Never leave a failed transparent/topmost test running.

## Commit & Pull Request Guidelines

History contains an initial import and `chore: normalize project.godot via Godot editor`; no broader convention is established. Use concise imperative subjects, optionally prefixed with `feat:`, `fix:`, or `chore:`. PRs should describe behavior changes, validation commands/results, relevant issues, and screenshots for UI/animation changes.

## Security & Asset Licensing

Keep `hook.py` silent on every path and exiting zero. Display only safe tool summaries. Never commit session data or credentials. Hook installation modifies `~/.claude/settings.json` with backups. Preserve the artwork attribution and CC BY-NC-SA 4.0 licensing documented in `README.md`.
