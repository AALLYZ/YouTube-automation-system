"""Visual stage: obtain one asset per scene, routed by visual_type."""
from __future__ import annotations

import os
import tempfile

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import AssetSource
from app.core.errors import AppError, ErrorCode
from app.core.logging import get_logger
from app.models.content import VideoScene
from app.models.media import VisualAsset
from app.providers.registry import get_image, get_stock, get_storage, get_video_clip
from app.services.ai_helpers import record_usage

log = get_logger("visuals")

_VERIFIED_LICENSES = {"generated-stub", "generated-stub-clip", "openai-generated"}


def _dims(aspect: str) -> tuple[int, int]:
    return {"16:9": (1920, 1080), "9:16": (1080, 1920), "1:1": (1080, 1080)}.get(aspect, (1920, 1080))


def run_visuals(
    db: Session, *, job_id: int, script_id: int, aspect: str = "16:9", visual_cfg: dict | None = None
) -> list[VisualAsset]:
    visual_cfg = visual_cfg or {}
    style = visual_cfg.get("image_style", "")
    width, height = _dims(aspect)
    scenes = list(
        db.execute(
            select(VideoScene).where(VideoScene.script_id == script_id).order_by(VideoScene.scene_index)
        ).scalars()
    )
    if not scenes:
        raise AppError("No scenes to render visuals for", code=ErrorCode.MISSING_ASSET)

    db.execute(delete(VisualAsset).where(VisualAsset.job_id == job_id))
    storage = get_storage()
    assets: list[VisualAsset] = []

    with tempfile.TemporaryDirectory() as tmp:
        for sc in scenes:
            vtype = sc.visual_type.value
            prompt = sc.visual_prompt or sc.narration[:120]
            asset = _one_scene(db, tmp, storage, job_id, sc, vtype, prompt, style, width, height)
            assets.append(asset)

    db.flush()
    log.info("visuals: %d assets for job %s", len(assets), job_id)
    return assets


def _one_scene(db, tmp, storage, job_id, sc, vtype, prompt, style, width, height) -> VisualAsset:
    ext = "png"
    asset_type = "image"
    source = AssetSource.AI_IMAGE
    license_ = ""
    attribution = ""
    provider_name = ""
    is_video = False

    local = os.path.join(tmp, f"scene_{sc.scene_index}")

    if vtype == "stock":
        provider = get_stock()
        provider_name = provider.name
        kind = "video" if style == "video" else "photo"
        tmp_out = local + (".mp4" if kind == "video" else ".jpg")
        res = provider.search(prompt, kind=kind, out_path=tmp_out)
        if res is None:
            # graceful fallback to a generated image
            img = get_image().generate(prompt=prompt, out_path=local + ".png", width=width, height=height, style=style)
            record_usage(db, img.usage, job_id=job_id, stage="VISUALS")
            local_path, ext, license_, source, provider_name = local + ".png", "png", img.license, AssetSource.AI_IMAGE, get_image().name
        else:
            local_path = res.path
            ext = os.path.splitext(res.path)[1].lstrip(".") or ("mp4" if res.is_video else "jpg")
            license_, attribution, is_video = res.license, res.attribution, res.is_video
            asset_type = "video" if res.is_video else "image"
            source = AssetSource.STOCK
    elif vtype == "ai_video":
        provider = get_video_clip()
        provider_name = provider.name
        res = provider.generate(prompt=prompt, out_path=local + ".png", duration_sec=sc.planned_duration_sec)
        record_usage(db, res.usage, job_id=job_id, stage="VISUALS")
        local_path, ext, license_, source = local + ".png", "png", res.license, AssetSource.AI_VIDEO
    else:  # image / upload-not-supported-yet
        provider = get_image()
        provider_name = provider.name
        res = provider.generate(prompt=prompt, out_path=local + ".png", width=width, height=height, style=style)
        record_usage(db, res.usage, job_id=job_id, stage="VISUALS")
        local_path, ext, license_, source = local + ".png", "png", res.license, AssetSource.AI_IMAGE

    key = f"visuals/{job_id}/scene_{sc.scene_index}.{ext}"
    storage.put(local_path, key)

    rights_verified = license_ in _VERIFIED_LICENSES or "Pexels" in license_ or "pexels" in license_.lower()

    asset = VisualAsset(
        job_id=job_id,
        scene_id=sc.id,
        asset_type=asset_type,
        source=source,
        prompt=prompt,
        file_key=key,
        width=width,
        height=height,
        duration_sec=sc.planned_duration_sec if is_video else None,
        license=license_,
        attribution=attribution,
        rights_verified=rights_verified,
        provider=provider_name,
    )
    db.add(asset)
    db.flush()
    return asset
