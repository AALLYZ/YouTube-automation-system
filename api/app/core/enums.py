"""Central enum definitions used across models, schemas, and the pipeline."""
from __future__ import annotations

import enum


class StrEnum(str, enum.Enum):
    """str-backed enum that serialises to its value."""

    def __str__(self) -> str:  # pragma: no cover - trivial
        return self.value


class UserRole(StrEnum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"


class ApprovalMode(StrEnum):
    AUTO = "AUTO"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"
    MANUAL = "MANUAL"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobStepStatus(StrEnum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class Stage(StrEnum):
    TOPIC = "TOPIC"
    RESEARCH = "RESEARCH"
    SCRIPT = "SCRIPT"
    SCRIPT_QA = "SCRIPT_QA"
    VOICE = "VOICE"
    VISUALS = "VISUALS"
    SUBTITLES = "SUBTITLES"
    TIMELINE = "TIMELINE"
    RENDER = "RENDER"
    THUMBNAIL = "THUMBNAIL"
    METADATA = "METADATA"
    FINAL_QA = "FINAL_QA"
    APPROVAL_GATE = "APPROVAL_GATE"
    UPLOAD = "UPLOAD"
    NOTIFY = "NOTIFY"
    COMPLETE = "COMPLETE"


class TopicStatus(StrEnum):
    GENERATED = "GENERATED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    USED = "USED"


class ScriptStatus(StrEnum):
    DRAFT = "DRAFT"
    QA_FAILED = "QA_FAILED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    FINAL = "FINAL"


class AssetSource(StrEnum):
    AI_IMAGE = "ai_image"
    AI_VIDEO = "ai_video"
    STOCK = "stock"
    UPLOAD = "upload"


class VisualType(StrEnum):
    IMAGE = "image"
    AI_VIDEO = "ai_video"
    STOCK = "stock"
    UPLOAD = "upload"


class MusicSource(StrEnum):
    NONE = "none"
    UPLOADED = "uploaded"
    LICENSED = "licensed"
    GENERATED = "generated"


class VideoStatus(StrEnum):
    RENDERING = "rendering"
    READY = "ready"
    FAILED = "failed"


class PrivacyStatus(StrEnum):
    PRIVATE = "private"
    UNLISTED = "unlisted"
    PUBLIC = "public"


class UploadStatus(StrEnum):
    DRAFT = "draft"
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    SCHEDULED = "scheduled"
    PUBLISHED = "published"
    FAILED = "failed"


class NotificationEvent(StrEnum):
    JOB_STARTED = "job_started"
    VIDEO_READY = "video_ready"
    PUBLISHED = "published"
    ERROR = "error"


class NotificationStatus(StrEnum):
    QUEUED = "queued"
    SENT = "sent"
    DELIVERED = "delivered"
    READ = "read"
    FAILED = "failed"


class AspectRatio(StrEnum):
    WIDESCREEN = "16:9"
    VERTICAL = "9:16"
    SQUARE = "1:1"
