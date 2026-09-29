# 人工标注与评测

评测集至少覆盖：单人连续镜头、多人交叉/遮挡、摔倒与非摔倒相似动作。将原始视频、标注版本和运行配置一同保存。训练/调参视频不要同时充当最终展示测试集。

## 行为与异常时间段

将人工标注保存为 JSON 数组。每条记录含 `person_id`、`start_time`、`end_time` 和 `action`（行为）或 `event`（异常），时间单位为秒。`person_id` 必须对应预测结果中的身份编号；若只评估事件检测而不评估身份，可传 `--ignore-person-id`。

示例格式（仅说明字段，不是项目实测标注）：

```json
[{"person_id": 1, "event": "fall", "start_time": 10.0, "end_time": 12.0}]
```

评测现有预测：

```powershell
python -m evaluation.evaluate_events --ground-truth annotations\falls.json --predictions "data\results\视频名\behaviors\anomaly_segments.json" --label-key event --output reports\falls.json
python -m evaluation.evaluate_events --ground-truth annotations\actions.json --predictions "data\results\视频名\behaviors\behavior_segments.json" --label-key action --output reports\actions.json
```

默认同一 `person_id`、同一类别且时间段 IoU 不低于 0.3 才能一对一匹配。报告提供 TP/FP/FN、Precision/Recall/F1、匹配事件的平均起点与时长绝对误差。人工标注必须覆盖待评估的视频范围，否则漏标会被计作误报。

## 人物身份

逐帧人工标注为 JSON 数组，每项提供 `frame_id`、全视频稳定的真实人物 `person_id` 和像素坐标 `bbox:[x1,y1,x2,y2]`。帧号需与 `person_poses.json` 一致。

```json
[{"frame_id": 100, "person_id": "person_A", "bbox": [50, 60, 180, 330]}]
```

```powershell
python -m evaluation.evaluate_identity --ground-truth annotations\identity.json --predictions "data\results\视频名\poses\person_poses.json" --output reports\identity.json
```

预测框和真实框默认以 IoU 0.5 一对一匹配；同一真实人物匹配到不同预测 `person_id` 时累计一次 ID Switch。只统计人工标注帧，报告不声称 MOTA 或 IDF1。标注抽样越稀疏，越可能低估短暂的身份切换。
