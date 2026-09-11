from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.enums import TopicStatus


class GenerateTopicsRequest(BaseModel):
    count: int = Field(8, ge=1, le=25)


class TrendingTopicsRequest(BaseModel):
    region_code: str = Field("US", min_length=2, max_length=2)
    category_id: Optional[str] = None
    max_results: int = Field(10, ge=1, le=50)
    count: int = Field(6, ge=1, le=20)


class LinkTopicsRequest(BaseModel):
    url: str = Field(..., min_length=5, max_length=2000)
    count: int = Field(6, ge=1, le=20)


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
    source: str
    source_ref: Optional[dict[str, Any]]

    class Config:
        from_attributes = True


class TopicReject(BaseModel):
    reason: str = ""
