# FishPet — Claude Code 进度桌宠

一只置顶、可点击穿透的桌宠，显示本机 Claude Code 会话在干什么。打游戏时不用切回 VS Code 看进度。

## 快速使用

双击 `start_fishpet.bat`。桌宠出现在屏幕右下角，拖动可以挪位置，位置会自动记住。

| 状态 | 表现 |
|---|---|
| 待机中 | 轻轻上下浮动 |
| 干活中 | 摆动加快，气泡显示当前在改的文件 / 在跑的命令 |
| 等你点一下 | 弹跳 + 变黄，气泡提示需要确认 |
| 干完了 | 跳一下，气泡显示「干完啦 · 用时」 |

鼠标悬停展开面板：当前状态 / 当前动作 / 已用时间 / 工具调用次数 / 项目名。
右键角色打开菜单：退出、切换会话、取消固定。
角色和气泡以外的区域点击穿透，不会挡住下面的游戏窗口。

## 原理

```
Claude Code hooks ──> state/<session_id>.json ──> 桌宠（每 0.5 秒轮询）
                                              └─> 增量读取 transcript 拿当前工具
```

- `hook.py` 挂在 SessionStart / UserPromptSubmit / Stop / SessionEnd / Notification 上。
  只在这些生命周期节点跑，不挂 PreToolUse/PostToolUse，避免每次工具调用都起进程拖慢对话。
- `hook.py` 全程静默：`UserPromptSubmit` 的输出会被注入 Claude 上下文，所以任何情况下都不 print，异常也退出 0。
- 桌宠只显示工具名和安全摘要（文件名、命令描述），**不显示工具输出内容**，避免代码或密钥出现在桌面上。

## 当前形象

`game/assets/pet.png` 是从明进足校的 Spine 资源 `Resouce/Spine/FootballPlayer/player_01` 渲染出来的
一张透明 PNG（idle 姿势，205×332），作为等美术图期间的替代形象。

生成方式（一次性，产物已保存，运行时不需要 Spine）：
1. 把 `game/addons/spine-godot` 的 Windows 三个 dll + `.gdextension` 和 `player_01.{skel,atlas,png}` 临时复制进本工程；
2. 用 `SpineSprite` 加载骨架，播放 `idle`，渲染到 420×620 的透明 `SubViewport`；
3. 保存截图、按 alpha 包围盒裁切后覆盖 `game/assets/pet.png`；
4. 删掉临时复制的插件和骨架资源，重新 `--import`。

## 更换形象

1. 把角色图放到 `assets/pet.png`（建议纯色背景）。
2. 抠图并生成透明贴图：

```bat
"C:\Windows\py.exe" -3 preprocess.py assets\pet.png game\assets\pet.png
```

3. 重启桌宠。构图会自动按底边居中缩放（高度 292px）。

如果原图带水印或标题文字，`preprocess.py` 只会保留与角色相连的最大色块，孤立的文字/水印会被去掉；去掉后仍有残留时，先用图片工具裁掉再跑。

## 卸载

```bat
"C:\Windows\py.exe" -3 install_hooks.py --remove
```

然后删除本目录即可。安装时会在 `~/.claude/settings.json` 留一份 `settings.json.bak.<时间>` 备份。

## 文件

| 文件 | 作用 |
|---|---|
| `hook.py` | hooks 入口，写状态文件 |
| `install_hooks.py` | 合并 / 移除 `~/.claude/settings.json` 里的 hooks（幂等，自动备份） |
| `preprocess.py` | 抠背景 + 裁切，生成透明贴图 |
| `start_fishpet.bat` | 启动桌宠 |
| `install_startup.bat` | 可选：加到开机启动 |
| `state/` | 运行时状态，每个会话一个 json |
| `game/` | Godot 4.7 工程（`pet.gd` / `status_store.gd` / `transcript_tail.gd` / `silhouette.gd`） |

## 排错

- **背景是黑的 / 不是透明**：确认 `game/project.godot` 里 `gl_compatibility`、`window/size/transparent`、`per_pixel_transparency/allowed`、`viewport/transparent_background` 四项都在。仍不行就退回不透明圆角小卡片。
- **状态不动**：`state/` 目录里有没有新文件？没有就是 hooks 没生效——重启 Claude Code 会话（hooks 在会话启动时加载），或检查 `settings.json` 的 `hooks` 字段。
- **一直显示「等你点一下」**：批准权限后 Claude Code 不会触发 hook，桌宠靠 transcript 有新工具活动自动切回「干活中」；如果 transcript 没变化，等下一次 Stop 也会纠正。
- **找不到 Godot**：改 `start_fishpet.bat` 里的 `GODOT` 路径。
