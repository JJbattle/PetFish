# 坐姿拆件补画 · 2026-10-30

工具：内置 imagegen，透明背景。目标：补齐头部头发、双臂和本子；随后按用户要求使用仓库导出脚本拆件、等比配准与静态拼装。绘制参考为上一级 `pose_reference.png`。

## 完整提示

Create ONE transparent RIG PARTS ATLAS from this exact blue-haired maid seated-writing reference. Square canvas, four CLEARLY SEPARATED components in a 2x2 layout, each entirely inside its quadrant with at least 30px transparent gutters, no overlap, no grids/text. Preserve exact character/style, costume, proportions and writing pose, no redesign.
TOP LEFT: the COMPLETE HEAD including face, sleepy attentive open blue eyes looking down toward paper, maid headband, halo curl, ALL long flowing blue HAIR, and only a tiny neck overlap. No clothes, collar, chest bow, gem, torso, arm, hand, skirt, tail, cushion, book. Repaint all hair under where torso previously covered it as needed. This is same 3/4 seated forward/downward head, not a frontal replacement.
TOP RIGHT: ONLY the NEAR writing ARM (screen-left arm in reference), complete rounded shoulder cap through bent elbow, forearm, SINGLE white wrist cuff, and ONE hand gripping the same slender navy/gold PEN. The pen is included with the grip, with its golden nib visible pointing down and RIGHT, not crossing through fingers. Arm bends down at elbow then extends right toward page as in reference. Continuous navy long sleeve, no exposed arm skin except hand, no detached cuff, no body fragments. Extend shoulder root with cloth overlap.
BOTTOM LEFT: ONLY the OPEN NOTEBOOK lying relatively flat on knees, same viewing angle from above as reference, subtle upward slope to screen RIGHT, central gutter diagonal in perspective, two blank cream pages, thin navy cover underneath. NO hands, pen, writing, symbols, character or fabric. Reconstruct entire page contours where fingers covered them.
BOTTOM RIGHT: ONLY the FAR supporting ARM (screen-right in reference), full rounded shoulder cap, bent elbow, navy long sleeve through ONE white cuff to ONE hand, fingers naturally curled resting gently on opposite page edge. Same arm direction as reference: shoulder above-left of hand, elbow lower-right, hand near the upper surface of page. No pen, book or body fragments. Cloth overlap at shoulder.
Every component fully opaque in its own silhouette, true alpha outside, no floor/shadow/glow or background. Do not include assembled character or whale. Components can be independently scaled to fit quadrants while preserving their aspect ratios; entire head hair and entire arm silhouettes must remain visible and separate. This atlas will be cut into individual Spine attachments. Precisely two hands total across the atlas.

## 导出处理

保留上一级 parts_sheet.png 原稿。按透明连通区域拆出四个部件，加入既有坐垫与补全身体。实体内部 alpha>240 的接近不透明像素统一至255，边缘保留抗锯齿；头部按遮挡用途拆为前层与后发，边界留16原像素重叠，两层必须共用骨骼。最终装配以 kit/assembly.json 为准，不承诺与最早组合参考逐像素重合。

