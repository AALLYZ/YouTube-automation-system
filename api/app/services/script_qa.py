"""Automated script QA + bounded auto-revision loop."""
from __future__ import annotations

import re

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.enums import ScriptStatus
from app.core.logging import get_logger
from app.models.content import Research, Script, ScriptVersion
from app.providers.registry import get_ai
from app.services.ai_helpers import ai_json, record_usage
from app.services.script import WORDS_PER_SECOND, revise_script

log = get_logger("script_qa")

PASS_THRESHOLD = 75

_SYSTEM = (
    "You are a strict script editor. Evaluate a YouTube narration script. Return "
    "JSON: {passed:bool, score:0-100, issues:[str], recommendations:[str]}. "
    "Check: length vs target, grammar, repetition, unsupported factual claims "
    "(claims not in the research), awkward sentences, weak hook, pacing, presence "
    "of a clear CTA, prohibited content, copyright/trademark risk, internal "
    "consistency. passed is true only if score >= 75 and there are no critical issues."
)


def _deterministic_checks(version: ScriptVersion, target_sec: int) -> list[str]:
    issues: list[str] = []
    body = version.body_json
    full = body.get("full_text", "")
    if not body.get("hook"):
        issues.append("Missing hook")
    if not body.get("cta"):
        issues.append("Missing CTA")
    if not body.get("scenes"):
        issues.append("No scene plan")
    target_words = target_sec * WORDS_PER_SECOND
    if version.word_count < target_words * 0.6:
        issues.append(f"Script too short ({version.word_count} words, target ~{int(target_words)})")
    if version.word_count > target_words * 1.5:
        issues.append(f"Script too long ({version.word_count} words, target ~{int(target_words)})")
    # crude repetition check
    sentences = [s.strip().lower() for s in re.split(r"[.!?]", full) if len(s.strip()) > 15]
    if len(sentences) - len(set(sentences)) > 1:
        issues.append("Repeated sentences detected")
    return issues


def run_script_qa(
    db: Session,
    *,
    script: Script,
    job_id: int,
    research: Research | None,
    max_revisions: int | None = None,
) -> dict:
    max_revisions = settings.max_stage_retries if max_revisions is None else max_revisions
    ai = get_ai()
    research_facts = (
        "; ".join(f.get("claim", "") for f in (research.facts if research else [])) or "none"
    )

    version = _current_version(db, script)
    attempts = 0
    result: dict = {}

    while True:
        det_issues = _deterministic_checks(version, script.target_duration_sec)
        prompt = (
            f"Target duration: {script.target_duration_sec}s\n"
            f"Word count: {version.word_count}\n"
            f"Research-supported facts: {research_facts}\n"
            f"Automated checks flagged: {det_issues or 'none'}\n\n"
            f"Script JSON:\n{version.body_json}"
        )
        data, usages = ai_json(
            ai, system=_SYSTEM, prompt=prompt, task="script_qa", temperature=0.2
        )
        for u in usages:
            record_usage(db, u, job_id=job_id, stage="SCRIPT_QA")

        score = float(data.get("score", 0) or 0)
        issues = list(data.get("issues", [])) + det_issues
        passed = bool(data.get("passed")) and score >= PASS_THRESHOLD and not det_issues
        result = {
            "passed": passed,
            "score": score,
            "issues": issues,
            "recommendations": data.get("recommendations", []),
            "version": version.version,
            "revisions": attempts,
        }
        version.qa_result = result
        script.qa_score = score
        db.flush()

        if passed or attempts >= max_revisions:
            break
        attempts += 1
        log.info("script QA failed (score=%s) — revision %d/%d", score, attempts, max_revisions)
        version = revise_script(
            db, script=script, job_id=job_id, previous=version, qa_result=result
        )

    script.status = ScriptStatus.APPROVED if result["passed"] else ScriptStatus.QA_FAILED
    if result["passed"]:
        script.status = ScriptStatus.FINAL
    db.flush()
    log.info("script QA final: passed=%s score=%s after %d revisions",
             result["passed"], result["score"], attempts)
    return result


def _current_version(db: Session, script: Script) -> ScriptVersion:
    return (
        db.query(ScriptVersion)
        .filter(ScriptVersion.script_id == script.id, ScriptVersion.version == script.current_version)
        .one()
    )
