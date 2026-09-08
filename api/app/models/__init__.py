"""Import all models so Alembic + mappers see them."""
from app.db.base import Base
from app.models.channel import Channel, ChannelSettings, YouTubeCredential
from app.models.content import (
    Research,
    Script,
    ScriptVersion,
    Topic,
    VideoScene,
)
from app.models.job import Job, JobStep
from app.models.media import (
    MusicTrack,
    Thumbnail,
    VideoProject,
    VisualAsset,
    Voiceover,
)
from app.models.ops import ApiUsage, Notification, SchedulerRun, SystemLog
from app.models.user import User
from app.models.youtube import YoutubeUpload

__all__ = [
    "Base",
    "User",
    "Channel",
    "ChannelSettings",
    "YouTubeCredential",
    "Topic",
    "Research",
    "Script",
    "ScriptVersion",
    "VideoScene",
    "Voiceover",
    "VisualAsset",
    "MusicTrack",
    "Thumbnail",
    "VideoProject",
    "YoutubeUpload",
    "Job",
    "JobStep",
    "Notification",
    "ApiUsage",
    "SystemLog",
    "SchedulerRun",
]
