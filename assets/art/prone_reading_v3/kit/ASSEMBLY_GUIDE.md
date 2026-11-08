# 趴读 v3 装配

在 1536 × 1024 的画布上，最底层的 whale_cushion.png 与坐姿使用同一张图。其左上角为 (12, 384)，等比倍率约 0.906。reading、fluke、shoe_far、shoe_near 的原位坐标见 assembly.json，对整个角色统一加 (354, 0)。导入 prone_v3.json 时 root 已含此偏移。assembled.png 给出装配结果。带独立表情的版本见相邻 expressions 目录。

双膝藏在裙后，鞋子朝上。reading 中的头部权重向颈根和右侧衰减，书、双手和枕头接触区固定。尾鳍与鞋的根部也固定在 root。维持 4 秒阅读循环，头轻倾约 0.6°，尾尖延迟轻摆约 1°，一只脚偶尔点一下。

白色头饰顶至下巴约 528 px。游戏中整体倍率取站姿节点倍率 × 355/528，默认约 0.1394。画布右侧的透明空间留作配准，窗口定位和点击轮廓依据实画区域计算。

仓库根目录用 `python tools/prepare_prone_v3.py` 重建拆件，用 `python tools/build_pose_rigs.py` 重建游戏图集与点击轮廓。角色来源及授权见仓库 README。
