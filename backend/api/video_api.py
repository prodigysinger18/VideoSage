import mimetypes
import ntpath
import os
import re
import shutil
import uuid

from fastapi import APIRouter, File, Header, HTTPException, UploadFile
from fastapi.responses import StreamingResponse

from backend.database.connection import database
from backend.api.helpers import fetch_all, fetch_one
from backend.analysis_jobs import analysis_jobs
from core.config_loader import get_section, get_value, load_config, resolve_path
from database.sqlserver_manager import SQLServerManager

router = APIRouter(prefix="/api", tags=["videos"])


@router.post("/videos/upload")
def upload_video(file: UploadFile = File(...)) -> dict:
    filename = ntpath.basename(file.filename or "")
    if not filename or not re.search(r"\.(mp4|avi|mov|mkv|webm)$", filename, re.IGNORECASE):
        raise HTTPException(status_code=422, detail="仅支持 mp4、avi、mov、mkv、webm 视频文件")
    config = load_config()
    max_bytes = int(get_value(config, "backend.upload_max_size_mb", 1024)) * 1024 * 1024
    upload_dir = resolve_path(config, get_value(config, "paths.video_dir", "data/videos"))
    os.makedirs(upload_dir, exist_ok=True)
    stored_name = f"{uuid.uuid4().hex[:12]}_{filename}"
    path = os.path.abspath(os.path.join(upload_dir, stored_name))
    try:
        with open(path, "wb") as target:
            total_bytes = 0
            while chunk := file.file.read(1024 * 1024):
                total_bytes += len(chunk)
                if total_bytes > max_bytes:
                    raise HTTPException(status_code=413, detail="视频文件超过上传大小限制")
                target.write(chunk)
        import cv2
        capture = cv2.VideoCapture(path)
        try:
            if not capture.isOpened():
                raise HTTPException(status_code=422, detail="视频文件无法读取")
            fps = float(capture.get(cv2.CAP_PROP_FPS) or 0) or None
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0) or None
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0) or None
            frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            if not fps or not width or not height or not frame_count:
                raise HTTPException(status_code=422, detail="视频缺少有效的帧率或画面信息")
            duration = frame_count / fps
        finally:
            capture.release()
        cursor = database.get().cursor()
        try:
            cursor.execute("""INSERT INTO dbo.videos
                (video_name,video_path,fps,width,height,duration)
                OUTPUT INSERTED.video_id VALUES (?,?,?,?,?,?)""",
                (filename, path, fps, width, height, duration))
            video_id = int(cursor.fetchone()[0])
            database.get().commit()
        finally:
            cursor.close()
    except HTTPException:
        if os.path.exists(path):
            os.remove(path)
        raise
    except Exception as exc:
        if os.path.exists(path):
            os.remove(path)
        raise HTTPException(status_code=503, detail=f"视频上传失败：{exc}") from exc
    try:
        state = analysis_jobs.enqueue(video_id, path)
        return {"video_id": video_id, "filename": filename, "status": state["status"], "error": state["error"]}
    except Exception as exc:
        return {"video_id": video_id, "filename": filename, "status": "failed", "error": f"分析任务启动失败：{exc}"}


def _video_path(video_id: int) -> str:
    row = fetch_one(database.get(), "SELECT video_path FROM dbo.videos WHERE video_id=?", (video_id,))
    if row is None:
        raise HTTPException(status_code=404, detail="视频不存在")
    path = os.path.abspath(str(row["video_path"]))
    if not os.path.isfile(path):
        raise HTTPException(status_code=404, detail="视频文件不存在")
    return path


def _add_analysis_status(row: dict) -> dict:
    state = analysis_jobs.get(int(row["video_id"]))
    has_results = bool(row.pop("has_results", False))
    row["status"] = state["status"] if state else ("completed" if has_results else "pending")
    row["analysis_error"] = state.get("error") if state else None
    row["analysis_progress"] = state.get("progress") if state else (100.0 if has_results else None)
    row["processed_frames"] = state.get("processed_frames") if state else None
    row["total_frames"] = state.get("total_frames") if state else None
    row["active_tracks"] = state.get("active_tracks") if state else None
    row["deletable"] = _uploaded_paths(str(row["path"])) is not None
    return row


def _uploaded_paths(video_path: str) -> tuple[str, str] | None:
    config = load_config()
    video_root = os.path.realpath(resolve_path(config, get_value(config, "paths.video_dir", "data/videos")))
    results_root = os.path.realpath(resolve_path(config, get_value(config, "paths.results_dir", "data/results")))
    path = os.path.realpath(video_path)
    if os.path.normcase(os.path.dirname(path)) != os.path.normcase(video_root):
        return None
    if not re.fullmatch(r"[0-9a-f]{12}_.+\.(mp4|avi|mov|mkv|webm)", os.path.basename(path), re.IGNORECASE):
        return None
    result_dir = os.path.realpath(os.path.join(results_root, os.path.splitext(os.path.basename(path))[0]))
    if os.path.normcase(os.path.dirname(result_dir)) != os.path.normcase(results_root):
        return None
    return path, result_dir


@router.delete("/videos/{video_id}")
def delete_video(video_id: int) -> dict:
    reserved = False
    try:
        config = load_config()
        with SQLServerManager(get_section(config, "database")) as manager:
            cursor = manager.execute("SELECT video_path FROM dbo.videos WHERE video_id = ?", (video_id,))
            record = cursor.fetchone()
            cursor.close()
            if record is None:
                raise HTTPException(status_code=404, detail="视频不存在")
            targets = _uploaded_paths(str(record[0]))
            if targets is None:
                raise HTTPException(status_code=403, detail="只能删除通过网页上传的视频")
            if not analysis_jobs.begin_delete(video_id):
                raise HTTPException(status_code=409, detail="视频正在分析或删除中，请稍后重试")
            reserved = True
            try:
                cursor = manager.connection.cursor()
                try:
                    cursor.execute("DELETE a FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id WHERE p.video_id=?", (video_id,))
                    cursor.execute("DELETE b FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id WHERE p.video_id=?", (video_id,))
                    cursor.execute("DELETE FROM dbo.persons WHERE video_id=?", (video_id,))
                    cursor.execute("DELETE FROM dbo.videos WHERE video_id=?", (video_id,))
                    manager.connection.commit()
                except Exception:
                    manager.connection.rollback()
                    raise
                finally:
                    cursor.close()
            except Exception as exc:
                raise HTTPException(status_code=503, detail=f"删除数据库记录失败：{exc}") from exc
            warnings = []
            video_path, result_dir = targets
            try:
                if os.path.isfile(video_path):
                    os.remove(video_path)
            except OSError as exc:
                warnings.append(f"视频文件清理失败：{exc}")
            try:
                if os.path.isdir(result_dir):
                    shutil.rmtree(result_dir)
            except OSError as exc:
                warnings.append(f"分析结果清理失败：{exc}")
            try:
                analysis_jobs.remove_state(video_id)
            except OSError as exc:
                warnings.append(f"任务状态清理失败：{exc}")
            return {"video_id": video_id, "deleted": True, "warnings": warnings}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"删除视频失败：{exc}") from exc
    finally:
        if reserved:
            analysis_jobs.end_delete(video_id)


@router.post("/videos/{video_id}/analyze")
def analyze_video(video_id: int) -> dict:
    path = _video_path(video_id)
    try:
        return analysis_jobs.enqueue(video_id, path)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _file_chunk(path: str, start: int, length: int):
    with open(path, "rb") as handle:
        handle.seek(start)
        remaining = length
        while remaining > 0:
            chunk = handle.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            remaining -= len(chunk)
            yield chunk


@router.get("/videos")
def videos() -> list[dict]:
    try:
        rows = fetch_all(database.get(), """SELECT v.video_id, v.video_name AS filename,
            v.video_path AS path, v.duration, v.fps, v.width, v.height,
            CASE WHEN EXISTS (SELECT 1 FROM dbo.persons p WHERE p.video_id=v.video_id)
                 THEN 1 ELSE 0 END AS has_results,
            create_time AS created_time
            FROM dbo.videos v ORDER BY create_time DESC, video_id DESC""")
        return [_add_analysis_status(row) for row in rows]
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc


@router.get("/videos/{video_id}")
def video(video_id: int) -> dict:
    try:
        row = fetch_one(database.get(), """SELECT v.video_id, v.video_name AS filename,
            v.video_path AS path, v.duration, v.fps, v.width, v.height,
            CASE WHEN EXISTS (SELECT 1 FROM dbo.persons p WHERE p.video_id=v.video_id)
                 THEN 1 ELSE 0 END AS has_results,
            create_time AS created_time
            FROM dbo.videos v WHERE v.video_id = ?""", (video_id,))
        if row is None:
            raise HTTPException(status_code=404, detail="视频不存在")
        stats = fetch_one(database.get(), """SELECT
            (SELECT COUNT(*) FROM dbo.persons WHERE video_id = ?) AS person_count,
            (SELECT COUNT(*) FROM dbo.behaviors b JOIN dbo.persons p ON p.id=b.person_id WHERE p.video_id = ?) AS behavior_count,
            (SELECT COUNT(*) FROM dbo.anomalies a JOIN dbo.persons p ON p.id=a.person_id WHERE p.video_id = ?) AS anomaly_count""", (video_id, video_id, video_id))
        row.update(stats or {})
        return _add_analysis_status(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"数据库查询失败：{exc}") from exc


@router.get("/videos/{video_id}/stream")
def stream_video(video_id: int, range_header: str | None = Header(default=None, alias="Range")):
    path = _video_path(video_id)
    file_size = os.path.getsize(path)
    if file_size == 0:
        raise HTTPException(status_code=404, detail="视频文件为空")
    media_type = mimetypes.guess_type(path)[0] or "video/mp4"
    start, end = 0, file_size - 1
    if range_header:
        if not range_header.startswith("bytes="):
            raise HTTPException(status_code=416, detail="不支持的 Range 请求", headers={"Content-Range": f"bytes */{file_size}"})
        value = range_header.removeprefix("bytes=").split(",", 1)[0]
        first, _, last = value.partition("-")
        try:
            if not first and last:
                start = max(0, file_size - int(last))
            elif first:
                start = int(first)
            else:
                raise ValueError("缺少 Range 位置")
            end = int(last) if first and last else file_size - 1
        except ValueError as exc:
            raise HTTPException(status_code=416, detail="无效的 Range 请求", headers={"Content-Range": f"bytes */{file_size}"}) from exc
        if start < 0 or start >= file_size or end < start:
            raise HTTPException(status_code=416, detail="Range 超出视频范围", headers={"Content-Range": f"bytes */{file_size}"})
        end = min(end, file_size - 1)
    length = end - start + 1
    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(length),
        "Content-Disposition": "inline",
        "Cache-Control": "no-cache",
        "X-Content-Type-Options": "nosniff",
    }
    if range_header:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"
    return StreamingResponse(
        _file_chunk(path, start, length),
        status_code=206 if range_header else 200,
        media_type=media_type,
        headers=headers,
    )
