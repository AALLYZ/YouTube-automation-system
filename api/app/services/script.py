"""Script generation: structured script + scene list, stored as the source of truth."""
from __future__ import annotations

import re

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.core.enums import ScriptStatus, VisualType
from app.core.logging import get_logger
from app.models.content import Research, Script, ScriptVersion, Topic, VideoScene
from app.providers.registry import get_ai
from app.services.ai_helpers import ai_json, record_usage

log = get_logger("script")

WORDS_PER_SECOND = 2.5  # ~150 wpm narration

_SYSTEM = (
    "You are a senior YouTube scriptwriter. Write a tight, retention-optimised "
    "narration script and a matching scene plan. Return JSON: {hook, intro, main, "
    "transitions:[str], pattern_interrupts:[str], cta, ending, full_text, "
    "scenes:[{scene:int, narration:str, visual_prompt:str, visual_type:'image'|'ai_video'|'stock', "
    "duration:number, transition:str}]}. full_text must be the exact narration to "
    "be read aloud, in order. Use short sentences, strong hook, natural speech, "
    "minimal repetition. Do not invent statistics that are not in the research."
)

_REVISION_SYSTEM = (
    "You are revising a YouTube script to fix QA issues. Keep what works, fix the "
    "listed problems, keep the same JSON schema and target duration."
)


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w']+\b", text or ""))


def _build_body(data: dict) -> dict:
    return {
        "hook": data.get("hook", ""),
        "intro": data.get("intro", ""),
        "main": data.get("main", ""),
        "transitions": data.get("transitions", []),
        "pattern_interrupts": data.get("pattern_interrupts", []),
        "cta": data.get("cta", ""),
        "ending": data.get("ending", ""),
        "full_text": data.get("full_text")
        or " ".join(
            filter(
                None,
                [data.get("hook"), data.get("intro"), data.get("main"), data.get("cta"), data.get("ending")],
            )
        ),
        "scenes": data.get("scenes", []),
    }


def _research_block(research: Research | None) -> str:
    if not research:
        return "No research package provided."
    lines = [f"Summary: {research.summary}"]
    if research.facts:
        lines.append("Verified facts: " + "; ".join(f.get("claim", "") for f in research.facts))
    if research.opinions:
        lines.append("Opinions: " + "; ".join(map(str, research.opinions)))
    if research.assumptions:
        lines.append("Assumptions: " + "; ".join(map(str, research.assumptions)))
    return "\n".join(lines)


def generate_script(
    db: Session,
    *,
    topic: Topic,
    job_id: int,
    research: Research | None,
    target_duration_sec: int,
    tone: str,
    style: str,
    language: str,
) -> tuple[Script, ScriptVersion]:
    script = Script(
        job_id=job_id,
        topic_id=topic.id,
        status=ScriptStatus.DRAFT,
        target_duration_sec=target_duration_sec,
        tone=tone,
        style=style,
        language=language,
        current_version=0,
    )
    db.add(script)
    db.flush()

    prompt = (
        f"Topic: {topic.title}\n"
        f"Hook idea: {topic.hook}\n"
        f"Angle: {topic.angle}\n"
        f"Audience: {topic.audience}\n"
        f"Language: {language}\nTone: {tone}\nStorytelling style: {style}\n"
        f"Target duration: {target_duration_sec} seconds "
        f"(~{int(target_duration_sec * WORDS_PER_SECOND)} words of narration)\n\n"
        f"Research package:\n{_research_block(research)}\n"
    )

    ai = get_ai()
    data, usages = ai_json(ai, system=_SYSTEM, prompt=prompt, task="script", temperature=0.8)
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="SCRIPT")

    version = _persist_version(db, script, data, created_by="ai")
    log.info("script v%d generated for job %s (%d words)", version.version, job_id, version.word_count)
    return script, version


def revise_script(
    db: Session,
    *,
    script: Script,
    job_id: int,
    previous: ScriptVersion,
    qa_result: dict,
) -> ScriptVersion:
    ai = get_ai()
    prompt = (
        f"Target duration: {script.target_duration_sec} seconds\n"
        f"QA score: {qa_result.get('score')}\n"
        f"Issues to fix: {qa_result.get('issues')}\n"
        f"Recommendations: {qa_result.get('recommendations')}\n\n"
        f"Current script JSON:\n{previous.body_json}\n\n"
        f"Return the full corrected JSON. This is revision {previous.version}."
    )
    data, usages = ai_json(
        ai, system=_REVISION_SYSTEM, prompt=prompt, task="script_revision", temperature=0.6
    )
    for u in usages:
        record_usage(db, u, job_id=job_id, stage="SCRIPT_QA")
    return _persist_version(db, script, data, created_by="revision")


def _persist_version(db: Session, script: Script, data: dict, *, created_by: str) -> ScriptVersion:
    body = _build_body(data)
    version_no = script.current_version + 1
    wc = _word_count(body["full_text"])
    est = int(wc / WORDS_PER_SECOND) if wc else 0

    version = ScriptVersion(
        script_id=script.id,
        version=version_no,
        body_json=body,
        word_count=wc,
        est_duration_sec=est,
        created_by=created_by,
    )
    db.add(version)
    script.current_version = version_no
    db.flush()

    # rebuild scenes for this job from the latest version
    db.execute(delete(VideoScene).where(VideoScene.script_id == script.id))
    scenes = body.get("scenes") or []
    for i, sc in enumerate(scenes):
        vt = str(sc.get("visual_type", "image")).lower()
        vt = vt if vt in {v.value for v in VisualType} else "image"
        db.add(
            VideoScene(
                script_id=script.id,
                job_id=script.job_id,
                scene_index=int(sc.get("scene", i + 1)),
                narration=str(sc.get("narration", "")),
                visual_prompt=str(sc.get("visual_prompt", "")),
                visual_type=VisualType(vt),
                planned_duration_sec=float(sc.get("duration", 6) or 6),
                transition=str(sc.get("transition", "fade")),
                caption_text=str(sc.get("narration", "")),
            )
        )
    db.flush()
    return version
