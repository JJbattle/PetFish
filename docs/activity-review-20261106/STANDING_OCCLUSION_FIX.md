# 站姿腿根穿裙：已修正实际前裙槽顺序

2026-11-08。用户截图中，围裙下出现两块粉色大腿根，另有整条蓝色内衬盖住原裙。已复现同一正式 rig 的 `march:0.5` 峰值，修复并重新生成、导入正式资源。

## 根因与改动

`repair_layers()` 将真实前裙保留在 `body`，而 `skirt` 附件是1×1空图。接入腿包后，`SLOTS` 仍将 `body` 放在腿后，因此“腿→内衬→skirt”的排序没有真实前裙遮挡。

`tools/build_spine.py` 已把 `body` 移到左右腿、鞋、`skirt_inner` 之后、原 `skirt` 槽之前。现在实际后至前为：腿/鞋 → 内衬 → 前身体/前裙。没有靠缩短腿、移动裙子或重画服装处理。`base_anim()` 从同一 `SLOTS` 生成全部动作的 drawOrder 复位，因此切动作不会恢复旧排序。

已更新 `game/assets/pet_spine/pet.spine-json`，重新采样 `pet_silhouette.png`，并运行 `tools/import_assets.ps1` 导入成功。已运行的桌宠会缓存骨架，需重启后读取新资源；本次没有停止用户原有桌宠进程。

## 证据与范围

- `standing-occlusion-before-after.jpg`：同一 `march 0.5s`，修复前后对照，已目视。
- `standing-occlusion-loop-zoom.gif` / `standing-occlusion-loop-actual.gif`：同一 loop=true state 连续推进6秒、15fps、91帧；首帧及2/4/6秒最大通道差均0。中立、左右峰值、回落已看图。
- `standing-occlusion-validation.json`：骨骼、skin/网格权重、全部非 drawOrder 动画轨道均与修复前一致。
- 29个动画共630帧成功渲染并更新点击轮廓；选定前后对照帧中鞋袜下部 y≥830 的像素差均0，喝水 `drink_sip:0.5` 和展示 `present:1` 整幅像素差0。
- 修复仅验收本次裙根遮挡；不由此宣称 A 套60秒、所有新动作的运动学和 UI 全部完成。

验证命令：构建器、`preview_pose.py --all --silhouette` 与正式资源导入均成功。独立连续循环脚本和源帧位于 `tools/_debug/standing_occlusion_fix/`，前后单帧在 `tools/_debug/codex_preview/standing_occlusion_before` / `standing_occlusion_after`。

## 完整行为回归的既有阻塞

`python tools/verify_pet.py` 未通过：`tools/runtime_check.gd:137` 引用当前 `pet.gd` 已删除的 `PANEL_RECT` / `SETTINGS_RECT` / `BUBBLE_RECT` 常量，脚本在解析阶段失败。没有把这次失败计为通过，也未修改产品代码来迎合旧测试。该轮隔离子进程已按完整项目路径和 `res://runtime_check.tscn` 命令行确认身份并终止，未终止用户原有桌宠。
