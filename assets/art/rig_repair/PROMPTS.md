# 制作提示与来源

使用内置 imagegen 编辑工具，透明背景。所有选用结果均已复制入本目录；构建不依赖用户目录中的生成缓存。

以下五项记录接手阶段素材的制作约束摘要，非逐字调用日志：

1. **front_armless_v1**：以 `assets/art/pet_portrait.png` 为参考，移除左右两条完整手臂（袖子、袖口和手），补全露出的头发、裙装。保留脸、比例、服饰、脚和透明背景，供独立手臂覆盖。
2. **r34_armless_v1**：编辑 `angle_references/20261024-v1/pet_r34_reference.png`，移除两条手臂并自然补全底图，保留朝右的 3/4 角度、角色造型和透明背景。
3. **up_armless_v1**：编辑同目录 `pet_up_reference.png`，移除两条手臂，保留仰头的脸、下巴、颈部和完整头发，避免横向补片。
4. **drink_two_hands_v1**：以上述仰头图为编辑目标、五动作参考的喝水格为手势参考。两条手臂抬起，两只手一起捧住圆润白杯，杯沿贴嘴，杯底朝屏幕右侧，闭眼仰头喝水。保留角色一致性和透明背景。
5. **work_notebook_v1**：以正面角色为编辑目标、五动作参考的工作格为手势参考。屏幕左手握笔在打开的本子上写字，屏幕右手托住本子。深蓝封面留空，后续由仓库原生路径加入准确鲸鱼图标。双手与袖口自然连接。

## front_blink_v1 的完整提示

Edit the supplied transparent character sprite PRECISELY, preserving canvas, scale, registration, silhouette, hairstyle, every bang edge, costume, and armless rig-ready body EXACTLY. Change ONLY the two eyes: both eyes gently fully CLOSED for one natural blink, two delicate curved dark reddish-brown upper-lash lines at the middle/lower part of the original eye openings, no open-eye lash remaining above, no iris, no sclera. Relaxed neutral sleepy expression, same eyebrows and tiny neutral mouth. Preserve original soft peach skin shading and pink cheeks. The bangs must remain entirely unchanged and crisp. Do not add arms, hands, props, text, panels, or background. Return the same full-body transparent PNG, pixel-aligned as closely as possible to the input, high-quality anime painted style identical to source.

编辑目标：本目录 `front_armless_v1.png`。输出：`front_blink_v1.png`。

左右顾盼及低头表情的逐字提示另见 [GAZE_PROMPTS.md](GAZE_PROMPTS.md)。
