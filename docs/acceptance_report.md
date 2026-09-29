# 端到端验收记录

2026-09-28 在本机进行只读 SQL Server 与结果文件检查；未运行新的完整视频推理，也未通过浏览器重新上传视频。

| 视频 ID | 数据来源 | 文件/JSON/SQL 检查 | 结论 |
| --- | --- | --- | --- |
| 2 | 已有 `50个摔倒的动作.mp4` 结果 | 视频文件、`video_info.json` 路径、Pose、行为、性能文件均存在；SQL 中 3 个人物、66 个行为段、59 个异常段 | 已有结果链路通过只读核对 |
| 3 | 已上传的 `fde8fcd9e2d6_行走参考  各种各样的走.mp4` | 视频文件存在；无对应分析 JSON，SQL 中人物/行为/异常均为 0 | 尚未完成自动分析闭环 |

后端 API 使用临时视频文件和 mock 数据库的 HTTP 合约测试通过；这不等价于真实 SQL 上传和模型推理成功。下一次用网页上传短视频时，应依次看到 `queued -> analyzing -> importing -> completed`，随后运行：

```powershell
python -m scripts.verify_analysis --video-id <新视频ID>
```

若状态为 `failed`，记录页面错误信息并重试；若验收脚本 `passed=false`，不要把该视频计入成功案例。历史视频的性能数据见 [performance_report.md](performance_report.md)，准确率仍待人工标注后评估。
