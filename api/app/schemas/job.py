from __future__ import annotations

import datetime as dt
from typing import Any, Optional

from pydantic import BaseModel

from app.core.enums import JobStatus, Stage


class JobStepOut(BaseModel):
    stage: Stage
    status: str
    attempt: int
    error_code: Optional[str]
    error_message: Optional[str]
    duration_sec: Optional[float]
    output: Optional[dict[str, Any]]

    class Config:
        from_attributes = True


class JobOut(BaseModel):
    id: int
    public_id: str
    channel_id: int
    mode: str
    test_run: bool
    status: JobStatus
    current_stage: Stage
    progress_pct: int
    topic_id: Optional[int]
    error_code: Optional[str]
    error_message: Optional[str]
    total_cost_usd: float
    total_duration_sec: float
    started_at: Optional[dt.datetime]
    finished_at: Optional[dt.datetime]
    steps: list[JobStepOut] = []

    class Config:
        from_attributes = True
