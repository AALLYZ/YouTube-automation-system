import datetime as dt

import pytest

from app.core.enums import JobStatus
from app.models.channel import Channel
from app.models.job import Job
from app.providers.registry import get_storage
from app.services.retention import prune_artifacts


@pytest.fixture()
def old_completed_job(db, tmp_path):
    ch = Channel(name="Ret Co", slug="ret-co", niche="x")
    db.add(ch)
    db.flush()
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)
    job = Job(public_id="job_2026_90001", channel_id=ch.id, status=JobStatus.COMPLETED,
              finished_at=old)
    db.add(job)
    db.flush()
    # backdate created_at past the retention window
    db.execute(Job.__table__.update().where(Job.id == job.id).values(created_at=old))
    db.commit()

    storage = get_storage()
    for kind in ("videos", "visuals", "thumbnails", "voiceovers", "subtitles"):
        src = tmp_path / "f.bin"
        src.write_bytes(b"x" * 10)
        storage.put(str(src), f"{kind}/{job.id}/f.bin")
    return job


def test_prune_dry_run_lists_but_keeps(db, old_completed_job):
    storage = get_storage()
    res = prune_artifacts(db, days=30, dry_run=True)
    assert old_completed_job.public_id in res["jobs"]
    assert storage.exists(f"videos/{old_completed_job.id}/f.bin") is True
    db.refresh(old_completed_job)
    assert old_completed_job.artifacts_pruned_at is None


def test_prune_deletes_artifacts_and_is_idempotent(db, old_completed_job):
    storage = get_storage()
    res = prune_artifacts(db, days=30)
    assert res["job_count"] == 1
    assert res["files_removed"] >= 5
    assert storage.exists(f"videos/{old_completed_job.id}/f.bin") is False

    db.refresh(old_completed_job)
    assert old_completed_job.artifacts_pruned_at is not None

    again = prune_artifacts(db, days=30)
    assert again["job_count"] == 0  # already pruned


def test_prune_skips_recent_and_running_jobs(db):
    ch = Channel(name="Fresh Co", slug="fresh-co", niche="x")
    db.add(ch)
    db.flush()
    db.add(Job(public_id="job_2026_90010", channel_id=ch.id, status=JobStatus.COMPLETED,
               finished_at=dt.datetime.now(dt.timezone.utc)))
    old = dt.datetime.now(dt.timezone.utc) - dt.timedelta(days=90)
    running = Job(public_id="job_2026_90011", channel_id=ch.id, status=JobStatus.RUNNING)
    db.add(running)
    db.flush()
    db.execute(Job.__table__.update().where(Job.id == running.id).values(created_at=old))
    db.commit()

    res = prune_artifacts(db, days=30)
    assert res["job_count"] == 0
