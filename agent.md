你现在负责开发我的项目 `E:\VideoSage` 的**第二阶段：人体姿态与基础行为分析**。

请严格基于当前项目已有代码进行开发，不要推翻现有第一阶段架构，不要随意重构无关代码。

---

# 一、项目当前状态

这是一个独立的视频理解项目，不要使用我之前其他项目中的技术方案。

第一阶段已经完成：

```text
视频输入
↓
OpenCV 视频读取
↓
YOLO11 人物检测
↓
ByteTrack 多目标跟踪
↓
稳定的 person_id
↓
人物轨迹保存
```

当前已经能够得到人物跟踪结果。

第二阶段需要在此基础上继续开发：

```text
人物检测/跟踪结果
↓
YOLO11 Pose
↓
人体关键点
↓
姿态特征计算
↓
基础行为判断
↓
行为状态平滑
↓
行为时间段
↓
JSON结果
```

---

# 二、第二阶段最终目标

第二阶段暂时只识别三个基础行为：

```text
standing
walking
sitting
```

最终系统应该能够生成类似：

```json
[
    {
        "person_id": 2,
        "action": "standing",
        "start_time": 0.0,
        "end_time": 8.4,
        "confidence": 0.93
    },
    {
        "person_id": 2,
        "action": "walking",
        "start_time": 8.4,
        "end_time": 15.7,
        "confidence": 0.91
    },
    {
        "person_id": 2,
        "action": "sitting",
        "start_time": 15.7,
        "end_time": 31.2,
        "confidence": 0.94
    }
]
```

保存到：

```text
E:\VideoSage\data\results\behaviors\behavior_segments.json
```

最终能够支持后续类似：

```text
2号人物什么时候开始行走？
```

通过行为时间段数据找到：

```text
person_id = 2
action = walking
start_time = 8.4
```

---

# 三、技术约束

当前项目采用稳定、低依赖方案。

必须优先使用当前已有环境和依赖：

```text
Python
PyTorch
Ultralytics
YOLO11
YOLO11 Pose
ByteTrack
OpenCV
NumPy
```

当前环境已经可以正常使用：

```python
from ultralytics import YOLO
```

不要：

```text
❌ 安装 MMPose
❌ 安装 MMCV
❌ 安装 MMEngine
❌ 使用 SAM2
❌ 使用 GroundingDINO
❌ 使用 InternVideo2
❌ 使用 Qwen3-VL
❌ 使用 Milvus
❌ 使用 faster-whisper
❌ 引入其他大型视频模型
```

不要为了第二阶段重新创建 Python/Conda 环境。

不要随意升级：

```text
PyTorch
CUDA
Ultralytics
```

不要因为实现某个功能而引入不必要的新依赖。

---

# 四、开发前必须先检查现有项目

开始写代码之前，请先检查：

```text
E:\VideoSage
```

重点查看：

```text
main.py
config.yaml

video_processing/
detection/
tracking/
pipeline/
utils/
data/
models/
tests/
```

特别检查：

```text
tracking/bytetrack_tracker.py
tracking/track_manager.py
pipeline/video_pipeline.py
```

确认第一阶段实际输出的数据结构。

不要假设现有代码的数据结构。

第二阶段必须适配现有第一阶段代码。

---

# 五、第一项开发：YOLO11 Pose

创建：

```text
detection/yolo_pose.py
```

要求：

1. 使用 Ultralytics 的 YOLO11 Pose。
2. 模型路径采用配置驱动，不要把模型路径硬编码在业务逻辑中。
3. 默认模型可以使用：

```text
models/yolo/yolo11n-pose.pt
```

4. 支持 CUDA，如果 CUDA 可用则优先使用 GPU。
5. 不要每一帧重新加载模型。
6. 模型应该初始化一次并重复使用。
7. 尽量保持接口简单，方便后续 `analysis_pipeline.py` 调用。
8. 输出人体关键点及其 confidence。
9. 保留与 `person_id` 的关联。

需要考虑第一阶段 ByteTrack 的：

```text
person_id
bbox
frame_id
timestamp
```

使 Pose 结果能够对应到具体人物。

---

# 六、Pose 数据结构

请设计一个清晰、稳定的数据结构。

至少包含：

```python
{
    "person_id": 2,
    "timestamp": 4.16,
    "keypoints": [...],
    "confidence": ...
}
```

关键点最好统一成：

```text
[x, y, confidence]
```

如果当前项目已有统一的数据结构，应优先复用已有结构。

不要为了追求复杂的数据结构而过度设计。

---

# 七、Pose 工具模块

创建：

```text
analysis/pose/__init__.py
analysis/pose/pose_utils.py
analysis/pose/pose_features.py
```

## pose_utils.py

负责：

```text
关键点索引处理
关键点有效性判断
获取指定关键点
处理低 confidence 关键点
必要的坐标归一化
```

重点处理人体关键点：

```text
shoulder
hip
knee
ankle
```

不需要实现所有复杂人体姿态算法。

---

# 八、pose_features.py

负责把关键点转换成后续行为判断可以使用的特征。

至少考虑：

```text
人体中心
肩膀中心
髋部中心
左膝角度
右膝角度
躯干角度
左脚踝位置
右脚踝位置
bbox 高度
bbox 宽度
```

必要时可以加入合理的归一化特征。

注意：

不要直接在 `pose_features.py` 中判断：

```text
walking
standing
sitting
```

这个模块只负责：

```text
关键点
↓
姿态特征
```

行为判断交给 `action_analyzer.py`。

---

# 九、行为分析模块

创建：

```text
analysis/action/__init__.py
analysis/action/action_analyzer.py
analysis/action/behavior_state.py
analysis/action/behavior_smoother.py
analysis/action/behavior_segment.py
```

---

# 十、action_analyzer.py

负责判断：

```text
standing
walking
sitting
```

第一版采用：

```text
YOLO11 Pose关键点
+
人物bbox
+
ByteTrack人物轨迹
+
Python规则
+
时间序列
```

不要引入复杂动作识别模型。

---

## Standing

根据合理的姿态特征判断站立。

可以考虑：

```text
躯干接近垂直
双腿相对伸直
髋部、膝盖、脚踝位置关系
人物中心短时间内变化较小
```

输出：

```text
standing
```

---

## Sitting

根据合理的姿态特征判断坐姿。

可以考虑：

```text
膝盖弯曲
髋部位置下降
大腿/小腿角度变化
躯干与腿部的相对关系
```

输出：

```text
sitting
```

不要只通过 bbox 高度判断 sitting。

---

## Walking

这是第二阶段最重要的部分。

Walking 必须使用**时间序列信息**。

不能仅通过单帧判断：

```text
某一帧 = walking
```

至少结合：

```text
人物中心连续位移
脚踝位置变化
左右腿/脚的交替变化
连续多个时间窗口
```

例如：

```text
frame 100
center_x = 300

frame 110
center_x = 320

frame 120
center_x = 345

frame 130
center_x = 370
```

结合脚踝运动后再判断：

```text
walking
```

需要避免：

```text
人物只是站着轻微移动
人物检测框抖动
摄像机轻微抖动
```

导致误判为 walking。

因此 Walking 必须基于一定时间窗口。

---

# 十一、behavior_state.py

负责维护每一个 `person_id` 当前的行为状态。

例如：

```python
{
    "person_id": 2,
    "current_action": "walking",
    "candidate_action": "standing",
    "action_start_time": 8.4,
    "last_update_time": 9.2
}
```

要求：

每个人物单独维护状态：

```text
person_id = 1
person_id = 2
person_id = 3
...
```

不能把所有人物混在一个状态中。

---

# 十二、behavior_smoother.py

解决逐帧行为抖动问题。

例如原始结果：

```text
standing
standing
walking
standing
walking
walking
standing
walking
```

不能直接作为最终结果。

请实现合理的时间窗口平滑机制，例如：

```text
滑动窗口
+
多数投票
```

或者其他简单稳定的方法。

目标是让结果变成：

```text
standing
standing
walking
walking
walking
walking
walking
walking
```

不要设计得过度复杂。

---

# 十三、behavior_segment.py

负责把逐帧行为结果转换成时间段。

例如：

```text
0.0s standing
0.1s standing
0.2s standing
...
8.4s walking
8.5s walking
...
15.7s sitting
```

转换：

```json
[
    {
        "person_id": 2,
        "action": "standing",
        "start_time": 0.0,
        "end_time": 8.4,
        "confidence": 0.93
    },
    {
        "person_id": 2,
        "action": "walking",
        "start_time": 8.4,
        "end_time": 15.7,
        "confidence": 0.91
    }
]
```

要求：

1. 相同人物连续行为合并。
2. 短暂的错误行为不要产生大量碎片。
3. 每个时间段保存：

```text
person_id
action
start_time
end_time
confidence
```

4. 最终保存：

```text
data/results/behaviors/behavior_segments.json
```

目录不存在时自动创建。

---

# 十四、Pose结果保存

同时保存 Pose 级别结果：

```text
data/results/poses/person_poses.json
```

建议结构：

```json
[
    {
        "person_id": 2,
        "timestamp": 4.16,
        "keypoints": [...],
        "features": {
            "left_knee_angle": 174.2,
            "right_knee_angle": 169.8,
            "torso_angle": 5.2
        }
    }
]
```

注意：

不要无限保存没有意义的中间数据。

数据结构需要方便后续调试和分析。

---

# 十五、Pipeline整合

只有在上述模块结构清晰后，再修改：

```text
pipeline/analysis_pipeline.py
```

负责串联：

```text
Track结果
↓
YOLO11 Pose
↓
Pose features
↓
Action analyzer
↓
Behavior state
↓
Behavior smoother
↓
Behavior segment
↓
结果保存
```

`analysis_pipeline.py` 只负责流程编排。

不要把大量行为判断逻辑全部塞进 Pipeline。

---

# 十六、与现有 main.py 的关系

如果当前 `main.py` 已经承担第一阶段入口功能：

不要大幅重构。

只需要为第二阶段提供合理的调用入口。

例如最终可以形成：

```text
main.py
 ↓
video_pipeline
 ↓
analysis_pipeline
```

但是具体实现必须根据当前项目实际代码决定。

---

# 十七、配置文件

如果项目当前已经存在：

```text
config.yaml
```

请优先将以下参数配置化：

```text
pose模型路径
device
confidence threshold
行为分析窗口大小
行为平滑窗口
walking阈值
standing阈值
sitting阈值
结果保存路径
```

不要把这些全部硬编码在 Python 文件中。

但是也不要为了配置化而大规模修改已有配置系统。

---

# 十八、性能要求

代码需要考虑实际视频处理性能：

1. Pose 模型只加载一次。
2. 尽量使用 GPU。
3. 不要每帧创建新的模型对象。
4. 不要在每帧打印大量日志。
5. 不要每帧写一次磁盘文件。
6. 可以先在内存中累积结果，阶段结束后统一保存。
7. 不要在每帧执行不必要的 GPU 信息查询。
8. 如果项目已有：

```text
utils/performance.py
```

保持现有性能统计结构，不要随意删除。

---

# 十九、关于现有 utils

当前：

```text
utils/
├── config_loader.py
├── performance.py
└── visualization.py
```

这些文件保留。

不要删除。

如果确实需要修改：

```text
config_loader.py
```

用于读取新增配置。

如果确实需要修改：

```text
performance.py
```

可以用于统计：

```text
Pose推理耗时
FPS
```

但不要每帧收集复杂 GPU 信息。

如果需要可视化：

```text
visualization.py
```

可以增加 Pose/行为显示功能，但不是第二阶段的核心。

---

# 二十、不要做的事情

当前阶段明确不要做：

```text
❌ MMPose
❌ MMCV
❌ MMEngine
❌ SAM2
❌ GroundingDINO
❌ InternVideo2
❌ Qwen3-VL
❌ Milvus
❌ faster-whisper
❌ FastAPI
❌ Vue
❌ SQL Server
❌ LLM Agent
❌ 实时摄像头
❌ 复杂危险行为
❌ 穿搭识别
❌ 鞋子识别
❌ 袜子识别
```

这些属于后续阶段。

当前只把：

```text
YOLO11 Pose
+
standing
+
walking
+
sitting
+
时间段
```

做好。

---

# 二十一、测试要求

**你不需要帮我进行完整测试。**

测试部分由我自己完成。

你可以：

```text
检查语法
检查 import
检查明显的数据结构错误
检查代码之间的接口是否一致
```

但不要把主要工作变成测试。

不要要求我提供测试结果。

不要因为没有测试视频而停止开发。

如果某个地方无法通过实际视频验证，请按照当前项目结构实现，并明确告诉我需要我后续验证什么。

---

# 二十二、开发原则

请遵守：

```text
先阅读现有代码
↓
理解第一阶段数据结构
↓
最小修改
↓
新增第二阶段模块
↓
保持模块职责清晰
↓
避免过度设计
↓
不要引入不必要依赖
```

尤其不要为了“看起来高级”而加入复杂模型。

当前目标是：

> 稳定、能够运行、结构清晰、方便后续扩展。

---

# 二十三、开发完成后的输出要求

完成代码修改后，请**不要只告诉我“完成了”**。

请按照下面的格式输出工作内容：

## 1. 本次完成的工作

逐项说明：

```text
修改了哪些文件
新增了哪些文件
每个文件负责什么
```

例如：

```text
1. detection/yolo_pose.py
   - 新增YOLO11 Pose封装
   - 支持GPU
   - 输出person_id对应的人体关键点

2. analysis/pose/pose_utils.py
   - 处理关键点
   - 提供关键点有效性判断

3. analysis/pose/pose_features.py
   - 计算膝盖角度、躯干角度等姿态特征

4. analysis/action/action_analyzer.py
   - 实现standing/walking/sitting基础行为判断
```

---

## 2. 第二阶段完整流程

用流程图说明你实现后的代码流程：

```text
视频
↓
YOLO11
↓
ByteTrack
↓
person_id
↓
YOLO11 Pose
↓
关键点
↓
姿态特征
↓
行为分析
↓
行为平滑
↓
时间段合并
↓
behavior_segments.json
```

---

## 3. 核心数据结构

说明：

```text
Track结果是什么
Pose结果是什么
行为结果是什么
最终JSON是什么
```

给出实际代码中采用的数据结构。

---

## 4. 行为判断逻辑

分别说明：

```text
standing怎么判断
walking怎么判断
sitting怎么判断
```

特别解释：

```text
walking为什么必须使用时间序列
```

---

## 5. 修改文件清单

明确列出：

```text
新增：
xxx.py
xxx.py

修改：
xxx.py
xxx.py

未修改：
xxx.py
```

---

## 6. 依赖变化

明确说明：

```text
新增了什么Python依赖
是否安装了新的包
是否修改了PyTorch
是否修改了CUDA
是否修改了Ultralytics
```

如果没有新增依赖，请明确写：

```text
本阶段未新增第三方依赖。
```

---

## 7. 我需要自己测试什么

虽然测试由我完成，但请最后告诉我：

```text
我下一步应该运行哪个程序
需要准备什么视频
应该观察什么结果
出现什么结果说明第二阶段基本成功
```

例如：

```text
1. 运行主程序
2. 输入测试视频
3. 检查 person_poses.json
4. 检查 behavior_segments.json
5. 查看2号人物是否出现walking时间段
```

---

## 8. 当前阶段剩余工作

最后说明：

```text
第二阶段已经完成：
xxx

第二阶段还需要我自己验证：
xxx

第三阶段暂时不要做：
xxx
```

不要擅自继续开发第三阶段。

---

# 最重要的要求

请记住：

**你的任务是帮我完成第二阶段代码，不是替我测试项目。**

**不要修改无关模块。**

**不要引入MMPose等额外框架。**

**不要创建新的Conda环境。**

**不要升级核心依赖。**

**不要实现第三阶段功能。**

**先检查现有代码，再开始修改。**

**完成后必须详细告诉我“你具体做了什么、为什么这么做、修改了哪些文件、当前代码如何工作”。**
