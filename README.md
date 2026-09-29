# VideoSage

VideoSage 将视频输入、人物检测与跟踪、姿态/行为/异常/穿搭分析、SQL Server 查询和 Vue 问答界面连成一条链路。当前目标是本机单实例演示与可重复评估，不是已完成的生产级服务。

## 架构

```text
Vue 3 / Vite
    | HTTP
FastAPI 上传与查询
    | 单进程、单并发分析队列
YOLO11 -> ByteTrack -> IdentityManager -> YOLO11 Pose
    | 行为 / 异常 / 穿搭分析
data/results/<视频名>/ JSON -> ResultImporter -> SQL Server
    | Query Engine / Agent -> Vue
```

视频上传后写入 `dbo.videos`，后台任务依次变为 `queued`、`analyzing`、`importing`、`completed`；失败为 `failed`，前端可重试。任务状态保存在 `data/results/.jobs/<video_id>.json`。旧视频若没有任务状态文件，界面暂按已导入的人物记录判断。单进程内同一时刻只运行一个分析任务。

视频管理页可删除通过网页上传且未在分析中的视频。确认后会删除该视频对应的 SQL 人物、行为、异常记录，再清理视频文件、分析结果目录和任务状态；此操作不可恢复。原始导入视频不会显示删除按钮。若数据库删除失败，文件保持原样；若数据库已删除但文件清理失败，界面会显示警告。

## 本机环境

现有机器检查到：Python 3.12.9、PyTorch 2.9.1+cu126、Ultralytics 8.4.150、OpenCV 4.13.0.92、FastAPI 0.139.0、pyodbc 5.3.0、PyYAML 6.0.3、python-multipart 0.0.32。前端依赖版本以 `frontend/package-lock.json` 为准。代码不自动安装或升级上述依赖。

准备 SQL Server 和 `config.yaml` 中的 `database` 连接配置；确认模型文件在 `paths.model_path`、`paths.pose_model_path` 等配置位置。上传上限由 `backend.upload_max_size_mb` 控制。不要将真实数据库密码或 LLM Key 发布到公共仓库。

在 PowerShell 中从项目根目录启动：

```powershell
conda activate pytorch
cd E:\VideoSage
python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
cd E:\VideoSage\frontend
npm ci
npm run dev
```

打开 Vite 打印的地址。上传短视频后，列表会自动刷新任务状态。`npm ci` 仅在前端依赖尚未安装时执行；它需要网络下载。

## 验收

1. 打开 `/videos`，上传一个能被 OpenCV 读取的短视频，确认出现 `queued` 或 `analyzing`。
2. 等待 `completed`，进入详情页确认播放、人物列表、行为和异常；用 Agent 问一个可由此视频数据回答的问题。
3. 运行只读检查，`video_id` 可从详情页 URL 得到：

```powershell
python -m scripts.verify_analysis --video-id 1
```

该检查核对数据库关联、视频/结果文件、非空 Pose 和行为、入库数量、性能文件。失败时返回非零退出码。它不运行推理或改写数据库。若浏览器状态为 `failed`，先看错误原因，再点击“重新分析”。

当前只读验收的实际结果见 [验收记录](docs/acceptance_report.md)；历史视频通过，但此前上传的视频 ID 3 尚无分析结果，不能宣称新上传闭环已验收通过。

当前只读验收的实际结果见 [验收记录](docs/acceptance_report.md)；历史视频通过，但此前上传的视频 ID 3 尚无分析结果，不能宣称新上传闭环已验收通过。

不连接 SQL Server 的自动化测试：

```powershell
python -m unittest discover -s tests -v
cd frontend
npm run build
```

本机 `frontend/dist` 若因 Windows 权限无法写入，可用 `npx vite build --configLoader runner --outDir "$env:TEMP\videosage-vite-check"` 检查前端构建。

## 量化评估

评估必须使用人工标注；格式和命令见 [标注规范](docs/annotation_format.md)。现有 `evaluation/evaluate_tracking.py` 统计碎片，不等于真实 ID Switch。新增脚本分别计算事件 Precision/Recall/F1、起点/时长误差，以及基于逐帧框匹配的真实 ID 切换次数。没有标注时不报告准确率。

历史视频的一次处理性能见 [性能记录](docs/performance_report.md)。它不是多次重复试验，也不能用于宣称识别准确率。

## 已知边界

- 队列在 FastAPI 进程内运行；重启会将未完成任务标记为失败，需要手动重试。不要使用多个 Uvicorn worker 共享同一任务目录。
- 当前没有用户认证、配额或跨机器队列；只应在可信本机环境开放上传接口。
- 浏览器播放依赖浏览器支持的视频编码；文件扩展名或 OpenCV 可读取不保证所有浏览器都能解码。
- 现有 Stage 2 要求产生有效 Pose 和行为时间段；完全无人或检测失败的视频会显示任务失败，而不是生成空的分析结果。

## 工程化命令

汇总多个事件评测报告：

```powershell
python -m evaluation.aggregate_reports --reports "data/evaluation/*_report.json" --output data/evaluation/summary.json
```

初始化或校验 SQL Server 表结构：

```powershell
python -m scripts.init_database --config config.yaml
```

健康检查：

```powershell
curl http://127.0.0.1:8000/health/live
curl http://127.0.0.1:8000/health/ready
```

设置 `VIDEOSAGE_API_KEY` 后，除健康检查和 API 文档外的接口需要通过 `X-API-Key` 或 Bearer 请求头认证。日志会记录请求 ID、状态码、耗时和视频任务状态。
