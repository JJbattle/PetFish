# 五套活动动作：Spine 拆件交付 v1

**动态审查补充（2026-11-06）：** 现有 region 起稿直接加旋转关键帧会出现整臂刚转、膝切边和脚底漂浮。v1 是静态美术基底，不是已完成关节绑定。请先按根目录 [ACTIVITY_REWORK_COORDINATION.md](../../../ACTIVITY_REWORK_COORDINATION.md) 的单关节探针完成网格/权重/接触约束，再制作整套动作；动态缺口由美术侧按反馈补图，不能靠强拉图片解决。

2026-11-06。覆盖这两天的 **三套站姿 + 两套坐姿**。原分镜是合并图，未画出遮挡后的部分；本包使用内置 image_gen 按原角色/分镜补画了可分层母版，再做确定性拆分与配准。不是简单裁掉分镜文字，也不是五份整人图片。

已交付：45 张透明 RGBA 部件图（含完整部件对照）、两套注册装配、Spine 4.2 静态导入 JSON、明暗底预览、头部替换检查、骨骼支点图、补画母版、提示词。缺失的常规活动美术已补在本包；动画制作者负责网格、权重、IK、动作与运行接入，不需要再从分镜抠人物或自己补画遮挡区。

**状态边界：** PNG 静态装配与 JSON 文件引用/骨骼父子顺序已检查；起稿只有 region 附件和骨骼，没有网格权重、IK、动画或 `.spine` 二进制工程。尚未在 Spine 编辑器或 Godot 验收动态。不要把“可导入起稿”写成“已做完动画”。

## 先打开这些文件

- `parts-overview.jpg`：全部透明拆件概览。
- `standing/assembled-light.jpg`、`standing/assembled-dark.jpg`：站姿装配。
- `seated/assembled-light.jpg`、`seated/assembled-dark.jpg`：坐姿装配。
- 两文件夹内 `binding-landmarks.jpg`：肩、肘、腕、腰、髋、膝、踝的起始位置。
- 两文件夹内 `head-variants-check.jpg`：正面、闭眼、左右中间姿态和目标姿态在身体上的实际装配。
- `standing/open-arms-check.jpg`：低位开掌手臂替换；`standing/heels-check.jpg`：鞋部替换配对检查。
- `standing/setup.json`、`seated/setup.json`：编辑器数据导入。`.spine-json` 为同内容副本，方便既有项目流程识别。

## 五张分镜怎么对应拆件

| 动作 | 使用起稿 | 美术能力 |
| --- | --- | --- |
| 小鱼原地巡逻 | standing | 双腿分为大腿、小腿、鞋；可做小幅屈膝踏步，提踵时换成配对鞋/小腿附件 |
| 海草舒展操 | standing | 上衣与裙摆分层，腰部重叠；左右连续袖子；低位开掌手臂变体 |
| 肩膀下班，脚步上班 | standing | 肩带/连续袖子做轻耸肩，复用分腿踏步和低位开掌 |
| 小鱼看看两边 | seated | 专用椅上坐姿、稳定椅子与双腿；头部左右中间/目标附件，可小幅侧倾 |
| 肩膀松一松 | seated | 放腿上的手臂做肩部动作；开胸时复用低位开掌手臂变体 |

五套不需要画成五份重复骨架；两套姿势骨架配共用头发/头部/尾巴即可。准确节拍仍见根目录 `SPINE_ACTIVITY_HANDOFF.md` 和 `assets/art/seated_neck_shoulder_v1/README.md`。本包替代旧交接文档里“还需要补图”的常规活动缺口，不改 60 秒编排。

## 部件与显隐规则

`l/r` 均指屏幕左/右；用户按镜像方向跟做。不可拿角色解剖左右再次翻转。

| 路径/附件 | 用法 |
| --- | --- |
| `parts/common/head_front.png` | 默认头部，含脸/前发/头饰，不含垂到裙边的长后发 |
| `parts/common/head_closed.png` | 同一 head slot 的闭眼替换，不额外挂一张脸 |
| `parts/common/head_turn_left/right.png` | 左右转头目标附件，不是头部侧倾 |
| `parts/extra/head_*_step1/2.png` | 左右转头的中间附件；角度是视觉关键姿势，不保证是等角度采样 |
| `parts/common/hair_back.png` | 完整隐藏后发底图，在身体后面，根部跟 head；发梢可独立权重，不带动脸/裙摆 |
| `parts/common/tail.png` | 完整根部到尾鳍，放在身体后，根部跟 hip |
| `parts/{standing,seated}/bodice.png` | 上衣，与 skirt 有约 28 原图像素重叠；跟 torso/腰部控制 |
| `parts/{standing,seated}/skirt.png` | 完整裙摆/围裙底层，跟 hip；不让侧弯把鲸鱼图案拉扁 |
| `parts/{standing,seated}/arm_l/r.png` | 肩到腕的连续长袖与手掌；在同一网格中分别分配肩/肘/腕权重，不在肘处横切袖子 |
| `parts/standing/arm_open_l/r.png` | 低位开掌变体，站/坐共用；已挂在同一左右 arm slot 中，不能与默认臂同时显示 |
| `parts/{standing,seated}/thigh_l/r.png` | 大腿层，包含裙下的隐藏腿根 |
| `parts/{standing,seated}/calf_l/r.png` | 小腿/袜层，与 thigh、shoe 保留重叠 |
| `parts/{standing,seated}/shoe_l/r.png` | 普通鞋层，跟 foot；足底基准已注册 |
| `parts/extra/heel_l/r.png` | 提踵鞋部替换，去掉补图里重复的高袜口；和同侧 `calf_heel_l/r` 配对换 |
| `parts/standing/calf_heel_l/r.png` | 提踵配套小腿，裁掉普通鞋顶部残影，避免换鞋时重影；属于同一个 calf slot 的变体 |
| `parts/seated/chair.png` | 完整椅子底图，跟 root，椅子不随肩颈运动 |

**只作对照，不与分段附件一起挂出：** `body.png` 是 bodice+skirt 的完整母件；`leg_l/r_full.png` 是完整腿对照；`extra/heel_l/r_source.png` 是尚未去高袜口的补图母件。共 8 张对照图，其他 37 张是装配/变体附件。

分段图特意保留原部件的透明画布和原点；看起来有大片透明区是为了让同一套 pivot/position 精确复原。不要自行“裁紧后仍用旧 pivot”，可在图集打包时 trim 并保留偏移。拆出的关节边缘没有画新的黑色切线；重叠区应由正确图层遮挡，不能同时当两套完整肢体显示。

## Spine 4.2 导入与绑定

1. 解压时保留路径。编辑器用 Import Data 导入相应 `setup.json`，不是双击把 JSON 当 `.spine` 工程。Images 默认 `../parts/`，相对于各 setup 文件；找不到图时指向本包 `parts`，保留 common/standing/seated/extra 子路径。
2. 导入后先对齐 `assembled-light.jpg`。画布 1024×1024，地面约 y=920；assembly 使用左上角坐标、y 向下、顺时针为正；Spine JSON 已将 y/旋转符号转换，不要再次反号。装配 scale 是注册比例，不是动画拉长比例。
3. `assembly.json` 每一层记录文件、局部 pivot、画布 position、统一 scale 和显隐；静态起稿已建 hip→torso→head、肩→前臂→手、大腿→小腿→脚控制。先校准骨骼局部轴/长度，再设置网格和权重；初始骨骼不是最终权重方案。
4. 长袖保持一片连续网格，肩根锁在衣身、肘附近渐变、腕口跟手。手掌可在同一网格末端跟 hand；禁止把整臂 scale 拉长。开掌变体使用同样的肩肘腕目标，切换时先到相近手势，旧附件同帧关闭。
5. 腿部使用固定长度骨链；两脚交替小幅抬落，支撑脚地面锚点稳定。大腿/小腿的原图重叠区足够小幅屈膝，按膝形状调整网格，不能做参考范围之外的大幅高抬腿或深蹲。
6. 提踵用脚尖固定目标和抬跟/踝位移，配对切 calf_heel 与 heel，不能整人上移冒充，也不能让原鞋顶部残留。鞋部附件方向略向外，开始/结束在双脚稳定的边界切换，实际接触与轻微形变由绑定完成。
7. 转头按 `front → step1 → step2 → turn` 进入、反向回正，再换另一侧。使用单一 head slot 的附件时间线，禁止两张脸淡入造成重影。中间头姿之间可对头根做很小的连续位移/转动；不能横向压脸冒充透视。侧倾使用正面头的小角度旋转，后发根部跟随，躯干/椅子/双脚稳定。
8. 一次只显示一套身体与左右手脚；补图里的 neck、collar 都归身体，head 不含第二个衣领。坐姿不要直接套站姿腿长，图片已分别配准。与正式角色切换时按头高等比注册，不按含椅子的整张包围盒强行压缩。
9. 当前提供的是五套轻活动需要的常规素材；先完成这些动作，不额外扩大到夸张侧身、过头举臂、深蹲、自然坐下/站起的大幅动作。那些不是这五套的必要内容，不能拿现有图硬拉。

## 验收与交接

- 已检查 45 张 PNG 存在有效透明区和实心区，两个 setup 的父子骨骼顺序、默认附件、所有图片引用正确；结果见 `validation.json`。
- 站/坐静态与头部替换、明暗底、开掌/鞋部配对已目视查看。其余动作需要绑定后验证连续三轮、实际尺寸、放大关节、首尾、动作混合、轮廓和桌面交互；不能仅凭 PNG 宣称动态通过。
- 正式接入保持第 4 版喝水袖子、持续提醒、菜单/设置分工；坐姿只记录坐姿舒展，不调用 stand_up 冒充起身。完整提醒和中断规则沿用既有交接单。
- 生产游戏、原骨架与已有动画本轮未改动。绘图生成提示在 `PROMPTS.md`，补画母版在 `sources/`；复现裁切/装配用根目录 `tools/prepare_activity_kit.py`（Pillow、NumPy）。
- 角色原始署名、来源和 CC BY-NC-SA 4.0 授权继续沿用根目录 README。

## 可直接发给大肥鱼

> 五套动作的美术拆件已经交付在 `assets/art/activity_spine_kit_v1/`。先读本 README，再看站/坐 assembled-light 和 binding-landmarks，分别导入 standing/setup.json、seated/setup.json；Images 指向 parts。包内是透明分层与补画底图，不需要你重新画角色。请基于已配准附件做网格、权重、IK 与五套动作；长袖保持连续网格，腿按 thigh/calf/shoe 分段，开掌/头姿/提踵使用同 slot 的变体，不要把完整 body/leg 对照图再叠上。转头有左右中间姿态，提踵要同步切配对 calf_heel 与 heel。静态 JSON 没有动画，完成绑定后按既有 60 秒时间线制作并交连续预览。保持提醒/喝水基线，坐姿舒展不算起身；先检查小幅动作，再做运行接入。
