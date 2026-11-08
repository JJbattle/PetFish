# 趴读 v3 · 偷着乐

当前版本共用坐姿鲸鱼垫。下表为角色局部坐标，换算到最终画布时统一加 (354, 0)。face_setup.json 的 root 已包含该位移，垫子在最底层。

眼睛和嘴各有一个 Spine slot。两个 slot 默认都选 `neutral`。制作 2–3 秒的开心段时，将 `prone_eyes` 和 `prone_mouth` 同时切到 `happy`，结束时显式切回 `neutral`；适用状态为 slack。触发时机、冷却间隔和身体动作由动画接入方安排。

| slot | 中性 | 开心 | PNG 左上角（母图坐标） |
| --- | --- | --- | --- |
| prone_eyes | eyes_neutral.png | eyes_happy.png | (276, 486) |
| prone_mouth | mouth_neutral.png | mouth_happy.png | (463, 625) |

母图为 1536 × 1024，原点在左上，Y 向下。下巴中点约为 (500, 677)，白色头饰至下巴约 528 px。两组 PNG 保留网格所需的透明边。reading_base.png 仍以 (−3, 26) 为左上角，沿用原 reading 附件的尺寸和 mesh。对位数据见 alignment.json。

**Spine 装配。** 解压交付包，在 Spine 4.2 导入 face_setup.json，图片目录选解压目录。该文件包括原骨架和默认皮肤。游戏构建器将原有阅读循环添加到此骨架上。两个新 slot 的骨骼是 root，网格顶点复用原 reading 对应三角形的骨索引、局部坐标和权重。两种表情共用这一配准。在眼嘴周围保留了 8 px 的透明度过渡，用于点头时的线性过滤。

**重建。** 先运行 `python tools/prepare_prone_expressions.py` 输出裁件、网格、对照图及压缩包。再运行 `python tools/build_pose_rigs.py` 更新游戏资源。补画使用内置 imagegen，提示词见 PROMPT.md；角色授权沿用仓库 README。
