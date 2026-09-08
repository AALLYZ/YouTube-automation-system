import pytest

from app.core.enums import NotificationEvent, NotificationStatus
from app.models.channel import Channel, ChannelSettings
from app.models.ops import Notification
from app.providers.notifier.stub import StubNotifier
from app.providers.registry import reset_providers
from app.services import notifications as notif


@pytest.fixture()
def stub_notifier(monkeypatch):
    monkeypatch.setattr(notif.settings, "notifier_provider", "stub")
    monkeypatch.setattr(notif.settings, "whatsapp_to", None)
    reset_providers()
    StubNotifier.reset()
    yield StubNotifier
    reset_providers()
    StubNotifier.reset()


def _channel(db, *, events=None, recipient="+15550001111"):
    ch = Channel(name="Notif Co", slug=f"notif-{db.query(Channel).count()}", niche="x")
    ch.settings = ChannelSettings(
        notify_events=events if events is not None else ["job_started", "video_ready", "published", "error"],
        whatsapp_cfg={"to": recipient} if recipient else {},
    )
    db.add(ch)
    db.flush()
    return ch


def test_template_render_all_events():
    ctx = {"channel_name": "C", "topic": "T", "title": "Ti", "job_public_id": "job_x",
           "youtube_url": "https://youtu.be/x", "stage": "RENDER",
           "error_code": "RENDER_FAILED", "error_message": "boom"}
    for event in NotificationEvent:
        name, body = notif.render_template(event, ctx)
        assert name and body and len(body) > 10


def test_notify_respects_channel_preferences(db, stub_notifier):
    ch = _channel(db, events=["published"])
    assert notif.notify(db, event=NotificationEvent.VIDEO_READY, channel=ch) is None
    row = notif.notify(db, event=NotificationEvent.PUBLISHED, channel=ch, context={"title": "Hi"})
    assert row is not None and row.status == NotificationStatus.SENT
    assert len(stub_notifier.sent) == 1


def test_notify_force_overrides_preferences(db, stub_notifier):
    ch = _channel(db, events=[])
    row = notif.notify(db, event=NotificationEvent.ERROR, channel=ch, context={}, force=True)
    assert row is not None and row.status == NotificationStatus.SENT


def test_notify_dedup_per_job_event(db, stub_notifier):
    from app.models.job import Job

    ch = _channel(db)
    job = Job(public_id="job_2026_09001", channel_id=ch.id)
    db.add(job)
    db.flush()

    a = notif.notify(db, event=NotificationEvent.VIDEO_READY, channel=ch, job=job, context={"title": "V"})
    b = notif.notify(db, event=NotificationEvent.VIDEO_READY, channel=ch, job=job, context={"title": "V"})
    assert a.id == b.id
    assert db.query(Notification).filter_by(job_id=job.id, event=NotificationEvent.VIDEO_READY).count() == 1
    assert len(stub_notifier.sent) == 1


def test_notify_without_recipient_marks_failed(db, stub_notifier):
    ch = _channel(db, recipient=None)
    row = notif.notify(db, event=NotificationEvent.PUBLISHED, channel=ch, context={"title": "X"})
    assert row.status == NotificationStatus.FAILED
    assert "recipient" in (row.error or "")
    assert stub_notifier.sent == []


def test_test_endpoint_and_listing(client, auth, stub_notifier):
    cid = client.post("/api/channels", json={"name": "Endpoint Co", "niche": "x"}, headers=auth).json()["id"]
    client.put(
        f"/api/channels/{cid}/settings", json={"whatsapp_cfg": {"to": "+15551230000"}}, headers=auth
    )
    r = client.post("/api/notifications/test", json={"channel_id": cid, "event": "published"}, headers=auth)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["template"] == "published"
    assert body["status"] == "sent"

    lst = client.get(f"/api/notifications?channel_id={cid}", headers=auth).json()
    assert len(lst) == 1 and lst[0]["id"] == body["id"]


def test_twilio_webhook_updates_delivery_status(client, auth, db, stub_notifier):
    ch = _channel(db)
    row = notif.send_test(db, channel=ch, event=NotificationEvent.VIDEO_READY)
    db.commit()
    mid = row.provider_message_id
    assert mid

    resp = client.post(
        "/api/webhooks/twilio",
        data={"MessageSid": mid, "MessageStatus": "delivered"},
    )
    assert resp.status_code == 204

    db.expire_all()
    refreshed = db.get(Notification, row.id)
    assert refreshed.status == NotificationStatus.DELIVERED
    assert refreshed.delivered_at is not None

    # read is a forward move; queued would be ignored
    client.post("/api/webhooks/twilio", data={"MessageSid": mid, "MessageStatus": "read"})
    db.expire_all()
    assert db.get(Notification, row.id).status == NotificationStatus.READ
    client.post("/api/webhooks/twilio", data={"MessageSid": mid, "MessageStatus": "sent"})
    db.expire_all()
    assert db.get(Notification, row.id).status == NotificationStatus.READ


def test_meta_webhook_verification(client, monkeypatch):
    monkeypatch.setattr("app.core.config.settings.meta_verify_token", "sekret")
    ok = client.get(
        "/api/webhooks/meta",
        params={"hub.mode": "subscribe", "hub.verify_token": "sekret", "hub.challenge": "42"},
    )
    assert ok.status_code == 200 and ok.text == "42"
    bad = client.get(
        "/api/webhooks/meta",
        params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"},
    )
    assert bad.status_code == 403


def test_pipeline_emits_video_ready_and_published(client, auth, db, stub_notifier):
    cid = client.post(
        "/api/channels", json={"name": "Pipe Notif", "niche": "tiny history", "video_length_min": 1},
        headers=auth,
    ).json()["id"]
    client.put(
        f"/api/channels/{cid}/settings", json={"whatsapp_cfg": {"to": "+15559990000"}}, headers=auth
    )
    topics = client.post(f"/api/channels/{cid}/topics:generate", json={"count": 5}, headers=auth).json()
    job = client.post(
        f"/api/channels/{cid}/scripts:draft",
        json={"topic_id": topics[0]["id"], "test_run": True},
        headers=auth,
    ).json()["job_public_id"]
    client.post(f"/api/jobs/{job}/media:run", headers=auth)
    client.post(f"/api/jobs/{job}/publish:run", headers=auth)

    events = {n["event"] for n in client.get(f"/api/notifications?channel_id={cid}", headers=auth).json()}
    assert "video_ready" in events
    assert "published" in events
