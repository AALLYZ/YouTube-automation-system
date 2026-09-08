"""Helpers for calling the AI provider and persisting usage."""
from __future__ import annotations

import json
import re
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.ops import ApiUsage
from app.providers.base import AIProvider, AIResult, Usage

log = get_logger("ai")

_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.S)


def record_usage(
    db: Session, usage: Usage, *, job_id: Optional[int] = None, stage: Optional[str] = None
) -> None:
    db.add(
        ApiUsage(
            job_id=job_id,
            stage=stage,
            provider=usage.provider,
            model=usage.model,
            operation=usage.operation,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            units=usage.units,
            seconds=usage.seconds,
            est_cost_usd=usage.est_cost_usd,
        )
    )
    db.flush()


def _extract_json(text: str) -> Any:
    text = text.strip()
    m = _FENCE.search(text)
    if m:
        text = m.group(1).strip()
    # trim to outermost braces
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        text = text[start : end + 1]
    return json.loads(text)


def ai_json(
    ai: AIProvider,
    *,
    system: str,
    prompt: str,
    task: str,
    temperature: float = 0.7,
    max_tokens: int = 3000,
    model: Optional[str] = None,
) -> tuple[dict, list[Usage]]:
    """Call the provider expecting JSON; one self-repair retry on parse failure."""
    usages: list[Usage] = []
    res: AIResult = ai.complete(
        system=system,
        prompt=prompt,
        task=task,
        json_mode=True,
        temperature=temperature,
        max_tokens=max_tokens,
        model=model,
    )
    usages.append(res.usage)
    try:
        return _extract_json(res.text), usages
    except (json.JSONDecodeError, ValueError):
        log.warning("AI JSON parse failed for task=%s; attempting repair", task)

    repair = ai.complete(
        system="You fix malformed JSON. Output only the corrected JSON object.",
        prompt=f"Fix this into a single valid JSON object:\n\n{res.text}",
        task=f"{task}_repair",
        json_mode=True,
        temperature=0,
        max_tokens=max_tokens,
    )
    usages.append(repair.usage)
    try:
        return _extract_json(repair.text), usages
    except (json.JSONDecodeError, ValueError) as exc:
        raise AppError(
            f"AI returned unparseable JSON for {task}", code=ErrorCode.PROVIDER_BAD_RESPONSE
        ) from exc
