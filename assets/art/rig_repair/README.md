# 动画修复素材

这些透明 PNG 是根据本仓库角色原画制作的分层母版，通过内置 imagegen 生成；不是可直接替换整个 Spine 骨架的序列帧。

| 文件 | 用途 |
| --- | --- |
| `front_armless_v1.png` | 正面无手臂底图，避免移动手臂后露出原来的袖子 |
| `r34_armless_v1.png` | 朝屏幕右侧的 3/4 无手臂底图 |
| `up_armless_v1.png` | 仰头视角底图，与喝水姿势配套 |
| `drink_two_hands_v1.png` | 旧版对照，有重复袖口和错误裸露皮肤，不再用于构建 |
| `drink_two_hands_v2.png` | 当前喝水母版：连续深蓝长袖，每腕一个白色袖口 |
| `work_notebook_v1.png` | 握笔、打开的笔记本及支撑手母版；封面在构建时叠加官方鲸鱼路径 |
| `front_blink_v1.png` | 闭眼表情母版，仅提取眼部区域 |
| `front_left_v1.png` / `front_right_v1.png` | 左右顾盼，保持脸朝正面 |
| `front_down_v1.png` | 工作、摸鱼时的低头注视表情 |

`tools/rig_repair.py` 负责配准、按轮廓拆层、透明遮罩和网格权重。`tools/pose_refinement.py` 负责姿势编排。手和道具的显示必须在同一帧替换原手臂，不能用两套手互相淡入淡出。

第 3 版把喝水的左右袖子各保留为一个连续网格（`d_fore_l/r`），按肩根、上臂、肘部、前臂和腕口分配权重；原 `d_upper_l/r` 独立切片不再显示。只有关节附近短段布料过渡，主段跟随固定长度骨骼旋转。`drink_arms` 保留杯子与双手，`drink_lift` 旋转抬杯，两组 IK 让手腕贴住杯子。当前幅度是胸前附近到嘴边；从腰间端杯需要补画低位姿势。

摸鱼的抚摸臂使用 `slack_sleeve_r` 连续袖子网格，按原画边缘排除误带的裙摆。右手腕校准到原画袖口的 `(607, 676)`，道具上的抚摸目标位于 `(470, 607)` 附近，避开 IK 最小可达半径；不可把目标拉到肩膀附近导致肘部反折。入场、保持、退场使用同一前置图层，手腕与手掌在同帧替换。

鲸鱼道具和笔记本封面统一取自 `tools/deepseek_whale.py` 中的原生路径。角色来源和授权说明沿用根目录 `README.md`，不得移除。

制作提示见 [PROMPTS.md](PROMPTS.md)；长袖补画的逐字提示见 [DRINK_SLEEVE_PROMPT.md](DRINK_SLEEVE_PROMPT.md)。构建后运行 `python tools/preview_pose.py --all --silhouette`，再运行 `python tools/verify_pet.py`。
