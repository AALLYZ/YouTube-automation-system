import pytest

from app.utils.ffmpeg import probe


@pytest.fixture()
def drafted(client, auth):
    cid = client.post(
        "/api/channels",
        json={"name": "Tiny Docs", "niche": "micro history", "video_length_min": 1},
        headers=auth,
    ).json()["id"]
    topics = client.post(
        f"/api/channels/{cid}/topics:generate", json={"count": 5}, headers=auth
    ).json()
    body = client.post(
        f"/api/channels/{cid}/scripts:draft",
        json={"topic_id": topics[0]["id"], "test_run": True},
        headers=auth,
    ).json()
    return cid, body["job_public_id"]


def test_full_media_pipeline_produces_playable_mp4(client, auth, drafted):
    _cid, job = drafted
    r = client.post(f"/api/jobs/{job}/media:run", headers=auth)
    assert r.status_code == 200, r.text
    results = r.json()["results"]
    assert results["voice"]["duration_sec"] > 1
    assert results["visuals"]["assets"] >= 3
    assert results["subtitles"]["cues"] >= 3
    assert results["render"]["size_bytes"] > 1000

    # job reflects progress
    jr = client.get(f"/api/jobs/{job}", headers=auth).json()
    assert jr["current_stage"] == "RENDER"
    stages = {s["stage"]: s["status"] for s in jr["steps"]}
    assert stages["RENDER"] == "SUCCEEDED"

    # timeline is retrievable and deterministic-shaped
    tl = client.get(f"/api/jobs/{job}/timeline", headers=auth).json()
    assert tl["fps"] == 30
    assert len(tl["scenes"]) >= 3
    assert abs(sum(s["duration"] for s in tl["scenes"]) - tl["duration"]) < 0.5

    # video streams and probes as real media
    v = client.get(f"/api/jobs/{job}/video", headers=auth)
    assert v.status_code == 200
    assert v.headers["content-type"] == "video/mp4"
    path = f"/tmp/ytauto-test-{job}.mp4"
    open(path, "wb").write(v.content)
    info = probe(path)
    assert info["duration_sec"] > 1
    types = {s["type"] for s in info["streams"]}
    assert "video" in types and "audio" in types


def test_hd_default_and_4k_render_quality(client, auth, drafted):
    cid, job = drafted

    # default quality is HD (1080p on 16:9)
    r = client.post(f"/api/jobs/{job}/media:run", headers=auth)
    assert r.status_code == 200, r.text
    tl = client.get(f"/api/jobs/{job}/timeline", headers=auth).json()
    assert tl["resolution"] == "1920x1080"

    # switching a channel to 4K quality produces a 3840x2160 render
    client.put(
        f"/api/channels/{cid}/settings",
        json={"visual_cfg": {"quality": "4k"}},
        headers=auth,
    )
    topics = client.post(
        f"/api/channels/{cid}/topics:generate", json={"count": 5}, headers=auth
    ).json()
    draft = client.post(
        f"/api/channels/{cid}/scripts:draft",
        json={"topic_id": topics[0]["id"], "test_run": True},
        headers=auth,
    ).json()
    job4k = draft["job_public_id"]
    r4k = client.post(f"/api/jobs/{job4k}/media:run", headers=auth)
    assert r4k.status_code == 200, r4k.text
    tl4k = client.get(f"/api/jobs/{job4k}/timeline", headers=auth).json()
    assert tl4k["resolution"] == "3840x2160"
    assert tl4k["quality"] == "4k"

    v = client.get(f"/api/jobs/{job4k}/video", headers=auth)
    assert v.status_code == 200
    path = f"/tmp/ytauto-test-4k-{job4k}.mp4"
    open(path, "wb").write(v.content)
    info = probe(path)
    vstream = next(s for s in info["streams"] if s["type"] == "video")
    assert vstream["width"] == 3840
    assert vstream["height"] == 2160


def test_single_stage_runner(client, auth, drafted):
    _cid, job = drafted
    out = client.post(f"/api/jobs/{job}/stages/voice:run", headers=auth)
    assert out.status_code == 200
    assert out.json()["output"]["duration_sec"] > 1

    bad = client.post(f"/api/jobs/{job}/stages/bogus:run", headers=auth)
    assert bad.status_code == 400
