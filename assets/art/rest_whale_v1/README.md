# 抱鲸鱼侧躺休息 · 第 1 批素材包

本包为新绘制的侧躺姿势及拆件。**没有完成动画，也没有替换正式游戏资源。** 制作任务、验收和功能边界见仓库根目录 [SPINE_REST_HANDOFF.md](../../../SPINE_REST_HANDOFF.md)；全部心愿已并入 [项目总纲.md](../../../项目总纲.md)。

## 交给绑定使用的六张图

`head_sleep.png`、`body_legs_tail.png`、`arm_near.png`、`arm_far.png`、`pillow.png`、`whale.png`。

各图为独立 RGBA PNG，四周留透明边。两条手臂包含完整长袖、单个袖口和手；手掌没有另画在鲸鱼上。头部不再包含重复衣领。鲸鱼由仓库 `tools/deepseek_whale.py` 的原生路径导出，其他素材使用内置 imagegen 绘制；原画归属与许可沿用根目录 README。

## 如何开始

1. 查看 `parts-overview.jpg` 与 `assembled-check.jpg`。
2. 按 `assembly.json` 的屏幕坐标、支点、等比缩放、旋转与从后到前顺序装配；完整画布 1200×850。
3. 有 Spine 4.2 时可数据导入 `rest_setup.spine-json`，图像目录设为本目录；这是 region 附件构成的静态起稿，没有动作、IK 或网格权重，也不是可直接运行的生产导出包。未在 Spine 编辑器中验证导入。
4. 先做小幅呼吸循环，再按交接单分阶段增加能力。切勿直接覆盖 `game/assets/pet_spine/`。

`head_drowsy_reference.png` 仅为半睁眼参考，未配准，不进入第一版；头发暂与头部合并、尾巴暂与身体合并，不能直接做独立摆尾/甩发。`pose_reference.png` 是构图参考，最终装配以六个拆件为准。`parts_sheet_draft.png` 是重复衣领尚未修正的旧稿；最终母版为 `parts_sheet.png`。

## 复现与来源

仓库根目录运行 `python tools/prepare_rest_kit.py` 可从最终母版按透明连通区域导出拆件、静态装配和起稿 JSON。工具只操作本素材目录，不启动 Godot、不修改现有动作。完整生成提示见 [PROMPTS.md](PROMPTS.md)。

本轮完成了透明度/独立拆件数量、引用与静态装配核对；动态关节连接、姿势切换与游戏接入仍由制作方逐项验收。
