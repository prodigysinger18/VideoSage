"""视频信息查询。"""

from typing import Any, Optional


class VideoQuery:
    def __init__(self, connection: Any) -> None:
        self.connection = connection

    def get_video_info(self, video_id: int) -> Optional[dict]:
        cursor = self.connection.cursor()
        try:
            cursor.execute(
                """SELECT video_id, video_name, video_path, duration, fps, width, height
                   FROM dbo.videos WHERE video_id = ?""",
                (video_id,),
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return {
                "video_id": row[0], "video_name": row[1], "video_path": row[2],
                "duration": row[3], "fps": row[4],
                "resolution": {"width": row[5], "height": row[6]},
            }
        finally:
            cursor.close()
