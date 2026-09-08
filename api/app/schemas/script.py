from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field

from app.core.enums import ScriptStatus


class DraftScriptRequest(BaseModel):
    topic_id: int
    research_enabled: bool = True
    test_run: bool = True
    target_duration_sec: Optional[int] = Field(None, ge=30, le=3600)
    tone: Optional[str] = None
    style: Optional[str] = None


class SceneOut(BaseModel):
    scene_index: int
    narration: str
    visual_prompt: str
    visual_type: str
    planned_duration_sec: float
    transition: str

    class Config:
        from_attributes = True


class ScriptVersionOut(BaseModel):
    version: int
    word_count: int
    est_duration_sec: int
    created_by: str
    qa_result: Optional[dict[str, Any]]
    body_json: dict[str, Any]

    class Config:
        from_attributes = True


class ScriptOut(BaseModel):
    id: int
    job_id: int
    topic_id: int
    status: ScriptStatus
    target_duration_sec: int
    tone: str
    style: str
    language: str
    current_version: int
    qa_score: Optional[float]
    versions: list[ScriptVersionOut] = []
    scenes: list[SceneOut] = []

    class Config:
        from_attributes = True


class DraftScriptResponse(BaseModel):
    job_public_id: str
    script: ScriptOut
    qa: dict[str, Any]
