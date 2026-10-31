# FishPet — 日常习惯陪伴桌宠

一只置顶、可点击穿透的桌宠，提供喝水记录、久坐提醒、备忘录和闹钟，并保留本机 Claude Code 会话进度显示。

当前产品方向以日常习惯陪伴和简单互动为核心，后续增加轻量激励，并逐步沉淀可复用的桌宠框架。激励与框架拆分尚未实现；最新范围见 [项目总纲](项目总纲.md) 和 [框架规划](PRODUCT_FRAMEWORK.md)。

## 快速使用

双击 `start_fishpet.bat`。桌宠出现在屏幕右下角，拖动可以挪位置，位置会自动记住。

| 状态 | 表现 |
|---|---|
| 待机中 | 呼吸起伏、发丝和尾巴轻摆、偶尔眨眼 |
| 干活中 | 摇得更快、头微微低着，气泡显示当前在改的文件 / 在跑的命令 |
| 摸鱼中 | 会话闲置超过 10 分钟：眼睛半睁、缓慢漂浮，气泡「摸鱼中… 有事叫我」 |
| 等你点一下 | 头歪向一边、耳鳍张开、身体小幅弹动并泛黄，气泡提示需要确认 |
| 干完了 | 跳一下（压扁再弹起），气泡显示「干完啦 · 用时」 |

鼠标悬停展开面板：当前状态 / 当前动作 / 已用时间 / 工具调用次数 / 项目名 / 今日喝水与久坐时长。
右键角色打开菜单：喝水打卡、提醒设置、切换会话、取消固定、退出。
角色和气泡以外的区域点击穿透，不会挡住下面的游戏窗口。

## 提醒功能

右键 → **提醒设置** 打开设置卡片，四页：

| 页面 | 做什么 |
|---|---|
| 喝水 | 点「一口 / 一杯 / 大杯」记录饮水量，大肥鱼陪你一起喝（播放喝水动作）；到间隔没喝会提醒，目标与提示音可调，今日总量每天自动清零 |
| 久坐 | 连续坐满设定时长（默认 60 分钟）提醒起身，播放伸懒腰动作；点「我起来活动了」重置计时 |
| 闹钟 | 设定时间与备注，可选每天 / 工作日 / 仅一次；到点大肥鱼跳起来 + 响提示音 |
| 备忘 | 标题 + 详细内容 + 可选日期（YYYY-MM-DD）；到那天会在气泡里提醒一次，可勾选完成 |

设置保存在 `data/pet_data.json`（不进 git），只有桌宠在运行时才会计时提醒。
右键菜单的「喝水打卡」是快捷入口，直接记一杯 250 ml。

> 面板内直接回复 Claude Code 目前做不到：Claude Code 不会轮询外部文件，
> hooks 也只是单向读取。这里用气泡 + 动作提供提醒，回复仍需回到终端。

## 原理

```
Claude Code hooks ──> state/<session_id>.json ──> 桌宠（每 0.5 秒轮询）
                                              └─> 增量读取 transcript 拿当前工具

提醒引擎 ──> data/pet_data.json ──> 气泡 + Spine 动作（喝水 / 久坐 / 备忘 / 闹钟）
```

- `hook.py` 挂在 SessionStart / UserPromptSubmit / Stop / SessionEnd / Notification 上。
  只在这些生命周期节点跑，不挂 PreToolUse/PostToolUse，避免每次工具调用都起进程拖慢对话。
- `hook.py` 全程静默：`UserPromptSubmit` 的输出会被注入 Claude 上下文，所以任何情况下都不 print，异常也退出 0。
- 桌宠只显示工具名和安全摘要（文件名、命令描述），**不显示工具输出内容**，避免代码或密钥出现在桌面上。

## 当前形象：Spine 骨骼版

`game/assets/pet_spine/` 是一个真正的 Spine 4.2 骨骼动画（`spine-godot` 4.2 GDExtension 运行时），
不是逐帧图片：网格随骨骼形变，待机时的呼吸、发丝摆动、尾巴摇动、眨眼都是骨骼驱动的。

- 底图：`assets/art/pet_portrait.png`（1024×1024 透明）
- 骨架：`tools/build_spine.py` 用纯 PIL 生成 `pet.spine-json` / `pet.atlas` / `pet.png`
  - 分层立绘 21 张（头发左右、身体、裙摆、鲸尾、上下臂、手掌、头、眼、嘴、杯子），每层独立网格
  - 23 根骨骼：root → hip → spine → chest → neck → head，头发 / 尾巴各三节，手臂 shoulder → forearm → hand
  - 权重只落在真实关节处；头、眼、嘴都是挂在 `head` 上的刚性层，不做网格形变，换表情不会把脸拉歪
  - 动画：`idle` / `working` / `slack` / `needs_input` / `done` / `cheer` / `stretch` / `water_remind` /
    `drink_in` / `drink_sip` / `drink_out`
  - 喝水按「拿杯 → 小口 × N → 放杯」串起来播；100 / 250 / 500 ml 分别对应 1 / 2 / 3 口，
    每口都是完整的 `drink_sip`，动作不会在半口被截断
- 重新生成：

```bat
python tools\build_spine.py
"D:\Godot_v4.7-stable_win64\Godot_v4.7-stable_win64_console.exe" --headless --path game --import
```

`game/tests/rig_test.tscn` 会把每段动画渲染成 PNG 到 `tools/_debug/frames/`，
`game/tests/pet_test.tscn` 用真实场景逐个状态截图，
`game/tests/feature_test.tscn` 截图设置卡片与提醒气泡，
`game/tests/reminders_test.tscn` 校验提醒逻辑（用 `tools/_debug/` 里的临时存档）。

> Spine 4.2 的 `rotate` 关键帧字段是 `"value"`，不是 `"angle"`；写成 `angle` 会被静默忽略。

### 形象版权

角色「溟月」，作者 **上善无形**（maid 设计 ZipZipPipe），
以 **CC BY-NC-SA 4.0** 授权使用：署名、非商业、相同方式共享。
二次创作的骨架/贴图沿用同一许可，**不可用于商业用途**。

## 卸载

```bat
python install_hooks.py --remove
```

然后删除本目录即可。安装时会在 `~/.claude/settings.json` 留一份 `settings.json.bak.<时间>` 备份。

## 文件

| 文件 | 作用 |
|---|---|
| `hook.py` | hooks 入口，写状态文件 |
| `install_hooks.py` | 合并 / 移除 `~/.claude/settings.json` 里的 hooks（幂等，自动备份） |
| `preprocess.py` | 抠背景 + 裁切（旧版平面贴图流程，Spine 版已不用） |
| `start_fishpet.bat` | 启动桌宠 |
| `install_startup.bat` | 可选：加到开机启动 |
| `state/` | 运行时状态，每个会话一个 json |
| `data/` | 提醒 / 备忘 / 喝水的持久化配置（`pet_data.json`，不进 git） |
| `tools/build_spine.py` | 生成 Spine 骨架、图集、网格权重与动画 |
| `game/` | Godot 4.7 工程（`pet.gd` / `reminders.gd` / `settings_panel.gd` / `status_store.gd` / `transcript_tail.gd` / `silhouette.gd`） |
| `game/addons/spine-godot/` | Spine 4.2 运行时（GDExtension） |
| `game/tests/` | 开发用截图/校验场景，不参与发布 |

## 排错

- **背景是黑的 / 不是透明**：确认 `game/project.godot` 里 `gl_compatibility`、`window/size/transparent`、`per_pixel_transparency/allowed`、`viewport/transparent_background` 四项都在。仍不行就退回不透明圆角小卡片。
- **状态不动**：`state/` 目录里有没有新文件？没有就是 hooks 没生效——重启 Claude Code 会话（hooks 在会话启动时加载），或检查 `settings.json` 的 `hooks` 字段。
- **一直显示「等你点一下」**：批准权限后 Claude Code 不会触发 hook，桌宠靠 transcript 有新工具活动自动切回「干活中」；如果 transcript 没变化，等下一次 Stop 也会纠正。
- **找不到 Godot**：改 `start_fishpet.bat` 里的 `GODOT` 路径。
- **提醒不响**：提醒只在桌宠运行时检查，关掉就没有后台服务；想重置所有设置就删 `data/pet_data.json`（下次启动会重新生成默认值）。
- **闹钟/备忘差一分钟**：检查间隔是 1 秒，同一分钟内只会响一次；一次性闹钟响完会自动关闭。
- **设置卡片点不动**：确认右键菜单 →「提醒设置」打开的是卡片本身；卡片外的点击会关闭它。
