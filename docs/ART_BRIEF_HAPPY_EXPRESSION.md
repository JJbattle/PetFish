# 表情需求：趴读（摸鱼 / slack）偶尔开心

给老师的一份「表情拆层 + 开心表情」清单。

已交付[拆件和装配说明](../assets/art/prone_reading_v3/expressions/README.md)与[完整素材包](prone-v3-expressions.zip)。游戏骨架默认中性，开心段可切换 `prone_eyes` / `prone_mouth` 的 `happy` 附件。

## 目标

日常保持现在的无口中性脸，**不用改**。只有「趴着看书 / 摸鱼（slack）」这个状态，
每隔一小段时间短暂流露出一小段开心，做出「偷着乐」的感觉。不是一直笑，是偶尔一小段，
播完自动回到中性。

## 为什么现在加不了表情

- 趴姿 v3 的脸画在 `reading` 一整张 mesh 里（prone 只有 reading / fluke / shoe_far /
  shoe_near 四个 mesh），**没有独立的脸 slot**。
- 坐姿 v2 的脸画在 `head_sit` 里，同样是整头一张图。
- 所以「换表情」目前等于「重画整张 reading / 整头」，既贵又会破坏已经调好的 mesh 权重。

## 需求：把脸拆成独立一层

请把脸（眼睛，可选加嘴）拆出来，做至少两组 attachment：

1. `neutral` —— 就是现在的脸，原样。
2. `happy` —— 开心脸：`^ ^` 弯眼（或满足地半闭眼），加一个小弧度的嘴角。**克制**，
   别做成表情包。

硬性约束：

- 眼睛 / 嘴必须精确落在原脸对应位置上，跟头一起动，不能漂移。
- 头的大小、角度、画风完全不变（趴读 v3 白色头饰顶到下巴 528 px 不变）。
- 拆出脸之后，`reading` 剩余部分还是原 mesh，权重不动。

## 交付物（按老师方便任选一种）

- **首选**：脸层透明 PNG（眼睛 neutral / happy，嘴 happy；neutral 可无嘴）
  + 每张的对位坐标（相对哪张画布、以头的哪个特征点对齐）。
- **退一步**：如果拆脸太麻烦，给一张「开心版 reading 整图」（同尺寸、同 mesh 结构、只改脸），
  我这边做成第二套 mesh attachment 来切换。

## 范围与优先级

- 本次**只做趴姿（slack）**。站姿、坐姿以后复用这套脸层，不在本次范围。
- 触发交给代码：中性 `prone_read_loop` 为主，偶尔插一段 2~3 s 的 happy beat
  （开心脸 + 一点小晃动），播完自动回中性，频率可调。身体的晃动我在 Spine 里用骨骼做，
  不需要新图，只缺脸。

## 可选：imagegen 提示

如果走 imagegen，建议**小范围手改**，不要整图重画（会破坏权重和对位）：

> Edit this prone-reading sprite's face only. Add a quiet, content "happy" expression:
> both eyes closed in gentle upward arcs (^^), a small soft smile, cheeks relaxed.
> Keep the head shape, hairstyle, headdress, book, pillow, body pose, colors and line
> style exactly unchanged. Single transparent PNG, same canvas and scale as the input.
