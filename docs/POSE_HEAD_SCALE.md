# 坐姿与趴姿的整体缩放

大肥鱼接入时，以站姿的白色花边头饰最高点到下巴底缘的纵向距离为准。三个姿势均在静止帧测量，忽略呆毛、披发、鞋底和道具。以下像素为人工读数，允许约 2 px 的取点误差。

| 已拼装源图 | 头饰顶 y → 下巴 y | 头高 | 相对站姿原图的整体倍率 | 默认 Godot 节点绝对 scale |
| --- | --- | ---: | ---: | ---: |
| `assets/art/pet_portrait.png` | 176 → 531 | 355 px | 1.0000 | 0.20732 |
| `assets/art/whale_seated_work_v2/kit/assembled.png` | 166 → 545 | 379 px | 0.9367 | 0.19419 |
| `assets/art/prone_reading_v3/kit/assembled.png` | 149 → 677 | 528 px | 0.6723 | 0.13939 |

在 `game/scripts/pet.gd` 的 `_load_pet()` 中，先取站姿比例 `standing_scale = target_h / 820.0`。坐姿和趴姿的 X、Y 整体比例分别为 `standing_scale * 355.0 / 379.0` 与 `standing_scale * 355.0 / 528.0`。保留套件原有附件尺寸及各层装配倍率。书、枕头、鲸鱼和所有骨骼跟随整套缩放一次。

当前 `_make_rig()` 接收目标高度，再除以该姿势的包围盒高度。沿用此接口时，坐姿传 `SEATED_SRC_BBOX.size.y * standing_scale * 355.0 / 379.0`，趴姿传 `PRONE_SRC_BBOX.size.y * standing_scale * 355.0 / 528.0`。沿用已有居中、底线和点击轮廓计算。默认站高 170 px 时，坐姿目标高约 **155 px**（含鲸鱼坐垫），趴姿约 **127 px**。v2 使用新绘制的紧凑身体，坐姿包围盒高 798 px。项目已应用上述倍率。

切换静止帧，在同一窗口配置下量头饰到下巴，默认目标约 **74 屏幕像素**。再检查坐姿呆毛是否进气泡区，确认三种姿势的点击轮廓仍跟着角色。尺寸对照图为原素材按上述倍率离线合成，放大两倍展示。

![三姿势尺寸对照](pose-head-scale-comparison.png)
