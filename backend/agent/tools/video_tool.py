from backend.api.helpers import fetch_one


class VideoTool:
    def __init__(self, connection): self.connection = connection

    def get_info(self, video_id: int) -> dict:
        return fetch_one(self.connection, """SELECT video_id,video_name,duration,fps,width,height
            FROM dbo.videos WHERE video_id=?""", (video_id,)) or {}
