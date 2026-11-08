# 提醒招手

左臂原画取自内置 imagegen，参照 `assets/art/pet_portrait.png`，右臂水平镜像。两片都包含袖根、袖口和摊开的手掌。游戏按 `tools/rig_repair.py` 的配准装入站姿骨架，袖根固定在胸前，肘和腕分别控制摆动。`tools/pose_refinement.py` 定义提醒循环，右手慢 0.13 秒，腕部再慢 0.06 秒。

## 补画提示词

Paint one standalone 2D puppet arm for the reference chibi maid, transparent PNG. Reference is ONLY for the exact dark navy uniform fabric, tiny cream hand, gold wrist piping, white frilled cuff, anime outlines and matching soft shading. No body, head, props or other limbs. A short bent greeting arm for her SCREEN-LEFT side. Anatomy and outline like a softly rounded capital L: rounded shoulder attachment at lower RIGHT, upper arm extends horizontally to an elbow at lower LEFT, forearm rises up from elbow at about 85 degrees, white frilled cuff immediately below a small but legible OPEN palm facing the viewer, fingers pointing UP, thumb sticking out toward screen right. All 5 chibi fingers grouped naturally and slightly separated. Gesture is waving hello next to the cheek. Paint one continuous uninterrupted fully covered navy long sleeve connecting shoulder through elbow to cuff, small soft elbow folds, no gaps. Compact short arm; upper arm length roughly equal to elbow-to-wrist length. Entire sprite isolated centered with margin; simple original style for 170px desktop pet, no photorealism or exaggerated hand details, no motion lines, no shadows or text.
