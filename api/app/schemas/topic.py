from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from app.core.enums import TopicStatus


class GenerateTopicsRequest(BaseModel):
    count: int = Field(8, ge=1, le=25)


class TopicOut(BaseModel):
    id: int
    channel_id: int
    job_id: Optional[int]
    title: str
    hook: str
    angle: str
    audience: str
    estimated_interest: float
    uniqueness_score: float
    difficulty: float
    search_potential: float
    retention_potential: float
    competition: float
    total_score: float
    evergreen: bool
    status: TopicStatus
    rejected_reason: Optional[str]

    class Config:
        from_attributes = True


class TopicReject(BaseModel):
    reason: str = ""
