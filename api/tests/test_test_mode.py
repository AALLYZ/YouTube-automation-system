"""TEST mode: the whole pipeline runs with zero API keys and never publishes."""
import pytest

from app.core.enums import NotificationStatus
from app.models.channel import Channel, ChannelSettings
from app.models.job import Job
from app.models.ops import Notification
from app.providers.registry import reset_providers
from app.services import notifications as notif


@pytest.fixture()
def stub_notifier(monkeypatch):
    from app.providers.notifier.stub import StubNotifier

    monkeypatch.setattr(notif.settings, "notifier_provider", "stub")
    monkeypatch.setattr(notif.settings, "whatsapp_to", None)
    reset_providers()
    StubNotifier.reset()
    yield StubNotifier
    reset_providers()
    StubNotifier.reset()


def test_full_pipeline_runs_offline_and_uses_stub_upload(client, auth):
    cid = client.post(
        "/api/channels",
        json={"name": "TestMode Co", "niche": "tiny history", "video_length_min": 1},
        headers=auth,
    ).json()["id"]
    client.post(f"/api/channels/{cid}/topics:generate", json={"count": 4}, headers=auth)
    job = client.post(
        "/api/jobs", json={"channel_id": cid, "mode": "AUTO", "test_run": True}, headers=auth
    ).json()

    assert job["status"] == "COMPLETED"
    up = client.get(f"/api/jobs/{job['public_id']}/upload", headers=auth).json()
    assert up["youtube_video_id"].startswith("stub")  # never a real id
    assert up["status"] in ("uploaded", "published", "scheduled")


def test_test_mode_routes_real_whatsapp_to_console(db, monkeypatch):
    """A test_run job must not deliver via a real (paid) WhatsApp provider."""
    monkeypatch.setattr(notif.settings, "notifier_provider", "twilio")
    monkeypatch.setattr(notif.settings, "whatsapp_to", "+15550000000")
    reset_providers()

    ch = Channel(name="TM", slug="tm-notif", niche="x")
    ch.settings = ChannelSettings(notify_events=["published"], whatsapp_cfg={"to": "+15551112222"})
    db.add(ch)
    db.flush()
    job = Job(public_id="job_2026_77001", channel_id=ch.id, test_run=True)
    db.add(job)
    db.flush()

    called = {"twilio": False}
    import app.providers.notifier.twilio_wa as tw

    def boom(self):  # constructing the real client would already need creds
        called["twilio"] = True
        raise AssertionError("real Twilio provider must not be used in test mode")

    monkeypatch.setattr(tw.TwilioWhatsApp, "__init__", boom)

    row = notif.notify(db, event=notif.NotificationEvent.PUBLISHED, channel=ch, job=job,
                       context={"title": "x"})
    assert row is not None
    assert row.status == NotificationStatus.SENT
    assert "console" in row.provider
    assert called["twilio"] is False
    reset_providers()


def test_non_test_job_uses_configured_provider(db, stub_notifier):
    ch = Channel(name="Live", slug="live-notif", niche="x")
    ch.settings = ChannelSettings(notify_events=["published"], whatsapp_cfg={"to": "+15551112222"})
    db.add(ch)
    db.flush()
    job = Job(public_id="job_2026_77002", channel_id=ch.id, test_run=False)
    db.add(job)
    db.flush()

    row = notif.notify(db, event=notif.NotificationEvent.PUBLISHED, channel=ch, job=job,
                       context={"title": "x"})
    assert row.provider == "stub"
    assert len(stub_notifier.sent) == 1
