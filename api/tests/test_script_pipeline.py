import pytest


@pytest.fixture()
def channel_id(client, auth):
    return client.post(
        "/api/channels",
        json={"name": "History Bites", "niche": "world history", "video_length_min": 3},
        headers=auth,
    ).json()["id"]


@pytest.fixture()
def topic_id(client, auth, channel_id):
    topics = client.post(
        f"/api/channels/{channel_id}/topics:generate", json={"count": 6}, headers=auth
    ).json()
    return topics[0]["id"]


def test_draft_script_runs_research_script_qa(client, auth, channel_id, topic_id):
    r = client.post(
        f"/api/channels/{channel_id}/scripts:draft",
        json={"topic_id": topic_id, "research_enabled": True, "test_run": True},
        headers=auth,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["job_public_id"].startswith("job_")

    script = body["script"]
    assert script["status"] in ("FINAL", "QA_FAILED")
    assert script["current_version"] >= 1
    assert len(script["scenes"]) >= 3
    assert script["versions"][0]["word_count"] > 0

    qa = body["qa"]
    assert "passed" in qa and "score" in qa and "issues" in qa

    # topic is now marked USED
    topics = client.get(f"/api/channels/{channel_id}/topics", headers=auth).json()
    assert any(t["id"] == topic_id and t["status"] == "USED" for t in topics)


def test_get_script_by_id(client, auth, channel_id, topic_id):
    body = client.post(
        f"/api/channels/{channel_id}/scripts:draft",
        json={"topic_id": topic_id},
        headers=auth,
    ).json()
    sid = body["script"]["id"]
    got = client.get(f"/api/scripts/{sid}", headers=auth)
    assert got.status_code == 200
    assert got.json()["id"] == sid
