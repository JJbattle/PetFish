# 活动拆件 v2：ART-HEEL-01

2026-11-07。仅交付本次提踵鞋修复；不是覆盖 v1 的整套骨架。没有修改动画侧 builder、动画关键帧或生产游戏。

## 本次确认

旧 heel 附件有两个独立问题：接地低了约 4–5 px；鞋画成外撇方向，换图后底部接触带的横坐标相对普通鞋左右各跳约 14.5 px。仅把旧图上移可以校正高度，但不能同时校正朝向/踝位/接触横坐标。

本次内置 image_gen 重新画了正面、短袜连接的提踵鞋，保持普通鞋朝向与宽度。`heel_l.png`、`heel_r.png` 已从母版分离、清理孤立像素，并在小腿的重叠区去掉补图上沿的切口黑线；不增加第二个袜口。

## 接入所需文件

- `heel_l.png`、`heel_r.png`：新的透明附件；不能拿 reference_shoe 或母版替代。
- `ART_HEEL_01.json`：必须一起应用的 region 参数、源图校验与对应 slot。
- `heel-comparison.jpg`：普通站立、旧提踵、新提踵对照。
- `validation.json`：7 个时刻的接触坐标与袜踝中心线检查。
- `PROMPT_HEEL.md`、`heel_front_source.png`：完整绘图提示与补画母版。
- `reference_shoe_l/r.png`：从 v1 普通鞋 alpha 范围提取的配色/朝向参考，不用于提踵显示。

### 注册值（Spine，y 向上）

| slot / attachment | path 保留 | x | y | width | height |
| --- | --- | ---: | ---: | ---: | ---: |
| shoe_l / heel_l | extra/heel_l | 1.0 | -16.0 | 69 | 80 |
| shoe_r / heel_r | extra/heel_r | -1.5 | -16.0 | 69 | 80 |

单位是当前 1024 源画布的骨架单位。不要只替换 PNG 而继续使用旧的 90×77 和 y=-25.04，否则会再次出现大小/接地偏差。不要移动整个 foot 骨来修图片注册；保留已经通过的 hip +5 / foot -5 探针作为本次基线，calf_heel 配对切换不变。

在动画侧 `build_activity_spine.py` 读完 setup 后，将两条 heel region 更新为 manifest 的 `region` 字段；在 atlas_sources 的图像加载阶段，仅把 `extra/heel_l`、`extra/heel_r` 的文件来源改到 v2 PNG。其余图片仍从 v1 加载。不要覆盖 v1 setup/PNG，给新版本显式选项。

示意接法（插入现有 builder，不改动画）：

```python
patch = json.loads((ROOT / 'assets/art/activity_spine_kit_v2/ART_HEEL_01.json').read_text())
image_overrides = {}
for change in patch['changes']:
    setup['skins'][0]['attachments'][change['slot']][change['attachment']].update(change['region'])
    image_overrides[change['path']] = ROOT / 'assets/art/activity_spine_kit_v2' / change['source_png']
# 图像加载处，将原 SRC / 'parts' / (src_path + '.png') 改为：
image_path = image_overrides.get(src_path, SRC / 'parts' / (src_path + '.png'))
```

## 实际验证范围

本轮以动画侧当前已加权袖子的 debug 导出为基线，只替换两张 heel 纹理及两组 region 注册参数，生成独立 `tools/_debug/activity_artfix_spine/`，通过独立、非置顶、限时项目 `activity_artfix_preview_proj` 真正渲染，不是离线摆图。

时刻 0、0.49、0.5、1、1.49、1.5、2 s：alpha>=128 的鞋底最低 y 均为 911；底部 3 行接触带横坐标中位数左 475.5、右 547.0，前后完全一致。袜踝中心线 y=810..890 无透明缺行。原反馈的 y=912 来自较低透明阈值的抗锯齿边缘，本报告统一阈值后比较；不是把地面随新鞋改掉。

这些只证明本次采样的接地注册与中心线连续性通过。不是脚尖的三维解剖定位，也不是完整提踵的最终验收：前视图的抬跟辨识度、袜踝侧缘、纹理/附件切换跳变、完整连续三轮、实际尺寸仍需动画侧检查。不要写“固定踝骨就证明脚尖固定”；foot 固定和图片接触位置必须同时检查。

手动复现：`python tools/patch_activity_heel_art.py --render`。该脚本只写 v2、activity_artfix_* 隔离输出，读取当前 debug 基线；不会覆盖 v1 或动画侧脚本。结果图帧在 `tools/_debug/activity_artfix_probe/`。

## 对三个探针的美术复核

1. 肘/腕：确认 mesh 和像素受前臂/手骨影响，机制通过；尚未证明“手在脸外侧”的招手目标姿势自然，不要继续沿用整臂 -125° 的旧 ready。
2. 单脚：确认支撑脚静止、横摆减少；放大图仍有膝盖的硬切边和突角，视觉未通过。优先用已有完整腿母件建立连续腿部网格验证，别把刚性片拼接当作完成；确实缺遮挡再向美术提交 ART-KNEE-L-01。
3. 提踵：原探针只证明位移抵消；本次追加了新鞋的实际接触位置核查。下一步可以接新鞋复验完整循环，但不能跳过切换瞬间和侧缘检查。

“不转 foot”是当前正面小动作的一种实现选择，不是所有提踵动画的通则；判断标准是接触点稳定、踝和小腿衔接自然、抬跟意图可读，不是是否使用某一个旋转轨道。

原角色来源、署名与 CC BY-NC-SA 4.0 要求沿用根目录 README。
