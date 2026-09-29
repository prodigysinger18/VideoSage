"""SQL Server 表结构定义。"""

CREATE_TABLE_STATEMENTS = (
    """
    IF OBJECT_ID(N'dbo.videos', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.videos (
            video_id INT IDENTITY(1,1) PRIMARY KEY,
            video_name NVARCHAR(255) NOT NULL,
            video_path NVARCHAR(500) NOT NULL,
            fps FLOAT NULL,
            width INT NULL,
            height INT NULL,
            duration FLOAT NULL,
            create_time DATETIME NOT NULL DEFAULT GETDATE()
        );
    END
    """,
    """
    IF OBJECT_ID(N'dbo.persons', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.persons (
            id INT IDENTITY(1,1) PRIMARY KEY,
            video_id INT NOT NULL,
            person_id INT NOT NULL,
            first_seen FLOAT NULL,
            last_seen FLOAT NULL,
            appearance_json NVARCHAR(MAX) NULL,
            CONSTRAINT FK_persons_videos FOREIGN KEY (video_id)
                REFERENCES dbo.videos(video_id),
            CONSTRAINT UQ_persons_video_person UNIQUE (video_id, person_id)
        );
    END
    """,
    """
    IF OBJECT_ID(N'dbo.behaviors', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.behaviors (
            id INT IDENTITY(1,1) PRIMARY KEY,
            person_id INT NOT NULL,
            action NVARCHAR(50) NOT NULL,
            start_time FLOAT NOT NULL,
            end_time FLOAT NOT NULL,
            confidence FLOAT NULL,
            CONSTRAINT FK_behaviors_persons FOREIGN KEY (person_id)
                REFERENCES dbo.persons(id),
            CONSTRAINT UQ_behaviors_segment UNIQUE
                (person_id, action, start_time, end_time)
        );
    END
    """,
    """
    IF OBJECT_ID(N'dbo.anomalies', N'U') IS NULL
    BEGIN
        CREATE TABLE dbo.anomalies (
            id INT IDENTITY(1,1) PRIMARY KEY,
            person_id INT NOT NULL,
            event NVARCHAR(50) NOT NULL,
            severity NVARCHAR(20) NULL,
            start_time FLOAT NOT NULL,
            end_time FLOAT NOT NULL,
            confidence FLOAT NULL,
            CONSTRAINT FK_anomalies_persons FOREIGN KEY (person_id)
                REFERENCES dbo.persons(id),
            CONSTRAINT UQ_anomalies_segment UNIQUE
                (person_id, event, start_time, end_time)
        );
    END
    """,
)
