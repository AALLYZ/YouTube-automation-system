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


def test_ai_video_scene_produces_real_video_asset(client, auth, drafted, db, monkeypatch):
    """A real text-to-video provider (not the offline stub) must be stored as a
    genuine video asset, not mislabeled as a still image (regression test for
    the hardcoded-.png bug in services/visuals.py)."""
    from sqlalchemy import select

    import app.services.visuals as visuals_mod
    from app.core.enums import VisualType
    from app.models.content import Script, VideoScene
    from app.models.media import VisualAsset
    from app.providers.base import ImageResult, Usage, VideoClipProvider

    _cid, job = drafted
    script = db.execute(select(Script).order_by(Script.id.desc())).scalars().first()
    scene = db.execute(
        select(VideoScene).where(VideoScene.script_id == script.id).order_by(VideoScene.scene_index)
    ).scalars().first()
    scene.visual_type = VisualType.AI_VIDEO
    db.commit()

    class FakeRealVideoProvider(VideoClipProvider):
        name = "fake_real_video"
        output_ext = "mp4"

        def generate(self, *, prompt: str, out_path: str, duration_sec: float = 4.0) -> ImageResult:
            with open(out_path, "wb") as fh:
                fh.write(b"FAKE_MP4_BYTES")
            return ImageResult(
                path=out_path, width=0, height=0,
                license="replicate-generated", attribution="",
                usage=Usage(provider="fake_real_video", operation="video_clip",
                            seconds=duration_sec, est_cost_usd=0.02),
            )

    monkeypatch.setattr(visuals_mod, "get_video_clip", lambda: FakeRealVideoProvider())

    r = client.post(f"/api/jobs/{job}/stages/visuals:run", headers=auth)
    assert r.status_code == 200, r.text

    asset = db.execute(select(VisualAsset).where(VisualAsset.scene_id == scene.id)).scalar_one()
    assert asset.asset_type == "video"
    assert asset.source.value == "ai_video"
    assert asset.file_key.endswith(".mp4")
    assert asset.duration_sec == scene.planned_duration_sec
    assert asset.rights_verified is True
    assert asset.provider == "fake_real_video"


def test_single_stage_runner(client, auth, drafted):
    _cid, job = drafted
    out = client.post(f"/api/jobs/{job}/stages/voice:run", headers=auth)
    assert out.status_code == 200
    assert out.json()["output"]["duration_sec"] > 1

    bad = client.post(f"/api/jobs/{job}/stages/bogus:run", headers=auth)
    assert bad.status_code == 400
