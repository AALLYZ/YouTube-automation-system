import datetime as dt

import pytest

from app.models.channel import Channel, ChannelSettings
from app.models.content import Topic
from app.models.job import Job
from app.scheduler import scheduler as sched


@pytest.fixture(autouse=True)
def no_pipeline_run(monkeypatch):
    """Scheduler tests exercise creation + dedup, not pipeline execution."""
    monkeypatch.setattr(sched.controller, "start", lambda db, job, **kw: job)


def _channel(db, *, automation=True, limit=2):
    ch = Channel(name="Sched Co", slug=f"sched-{db.query(Channel).count()}", niche="clocks",
                 video_length_min=1)
    ch.settings = ChannelSettings(automation_enabled=automation, daily_video_limit=limit,
                                  approval_mode="AUTO")
    db.add(ch)
    db.flush()
    for i in range(3):
        db.add(Topic(channel_id=ch.id, title=f"Sched topic {ch.id}-{i}", fingerprint=f"fp{ch.id}{i}",
                     total_score=50 + i))
    db.flush()
    return ch


def test_tick_creates_up_to_daily_limit(db):
    ch = _channel(db, limit=2)
    out = sched.tick_channel(db, ch)
    assert len(out["created"]) == 2
    assert db.query(Job).filter_by(channel_id=ch.id).count() == 2


def test_tick_is_deduped_per_day(db):
    ch = _channel(db, limit=2)
    first = sched.tick_channel(db, ch)
    assert len(first["created"]) == 2
    second = sched.tick_channel(db, ch)
    assert second["skipped"] == "already ran today"
    assert db.query(Job).filter_by(channel_id=ch.id).count() == 2


def test_tick_accounts_for_existing_jobs(db):
    ch = _channel(db, limit=3)
    db.add(Job(public_id="job_2026_88001", channel_id=ch.id))
    db.flush()
    out = sched.tick_channel(db, ch)
    assert len(out["created"]) == 2  # 3 limit - 1 existing
    assert out["already_had"] == 1


def test_tick_skips_when_automation_disabled(db):
    ch = _channel(db, automation=False)
    assert sched.tick_channel(db, ch)["skipped"] == "automation disabled"
    # force overrides
    forced = sched.tick_channel(db, ch, force=True)
    assert len(forced["created"]) == 2


def test_tick_all_runs_every_channel(db):
    _channel(db, limit=1)
    _channel(db, limit=1)
    results = sched.tick_all(db)
    assert len(results) == 2
    assert all(len(r.get("created", [])) == 1 for r in results)


def test_scheduler_run_endpoint(client, auth, db, monkeypatch):
    monkeypatch.setattr(sched.controller, "start", lambda db, job, **kw: job)
    ch = _channel(db, limit=1)
    db.commit()
    r = client.post(f"/api/scheduler/run?channel_id={ch.id}", headers=auth)
    assert r.status_code == 200
    assert len(r.json()["results"][0]["created"]) == 1

    runs = client.get(f"/api/scheduler/runs?channel_id={ch.id}", headers=auth).json()
    assert len(runs) == 1 and runs[0]["jobs_created"] == 1
