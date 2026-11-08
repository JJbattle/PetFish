# 鲸鱼坐垫写字 v2

用 `assembled.png` 核对静止姿势。头饰到下巴约 379 px，下巴到鞋底约 345 px，站姿的相应尺寸约为 355 和 420 px。坐姿双膝弯曲，鞋跟收在裙摆下。默认站高 170 px 时，整个坐姿连坐垫高约 155 px。

1. 七个透明附件的后前顺序及落点见 `assembly.json`。坐标原点在 1280 × 1280 画布左上角。pivot 为裁件内部坐标，position 为画布坐标，scale 等比，angle 顺时针。新身体与各层倍率配套使用。
2. `head_sit` 是连着长发的整头，放在身体后面。`chin` 是同一头图中遮住领口的一小块，和 `head_sit` 共用 `sit_head` 骨及变换。不要把这两片分别摆动。双臂在本子前，写字手与笔保持一体。
3. 运行 `python tools/build_pose_rigs.py` 将骨架、图集与点击轮廓生成到游戏。只做坐姿预览时，依次运行 `python tools/build_seated_spine.py` 和 `python tools/seated_preview.py`。游戏中进入 working 状态查看。
4. 对齐头部的整体倍率仍为站姿的 355/379；默认节点 scale 约为 0.19419。运行时已应用。笔尖与压页手需在关键帧保持纸面接触。

新身体使用内置 imagegen 补画，头、鲸鱼坐垫、本子和双臂取自上一版。原始授权见仓库 README。
