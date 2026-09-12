"""Real text-to-video provider via Replicate's hosted model API.

Uses the model-scoped predictions endpoint
(POST /v1/models/{owner}/{name}/predictions) so no version hash needs to be
pinned — swap to any other Replicate text-to-video model by changing the
REPLICATE_VIDEO_MODEL env var, no code changes needed. Prediction creation is
asynchronous, so `generate()` polls until the job finishes (or times out) and
downloads the resulting video to `out_path`.
"""
from __future__ import annotations

import time

import httpx

from app.core.config import settings
from app.core.errors import AppError, ErrorCode
from app.core.pricing import video_clip_cost
from app.providers.base import ImageResult, Usage, VideoClipProvider

_BASE = "https://api.replicate.com/v1"
_POLL_INTERVAL_SEC = 3
_POLL_TIMEOUT_SEC = 600


class ReplicateVideoClip(VideoClipProvider):
    name = "replicate"
    output_ext = "mp4"

    def __init__(self) -> None:
        if not settings.replicate_api_token:
            raise AppError("REPLICATE_API_TOKEN is not set", code=ErrorCode.CONFIG)
        self._token = settings.replicate_api_token
        self._model = settings.replicate_video_model

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    def generate(self, *, prompt: str, out_path: str, duration_sec: float = 4.0) -> ImageResult:
        try:
            resp = httpx.post(
                f"{_BASE}/models/{self._model}/predictions",
                headers=self._headers(),
                json={"input": {"prompt": prompt}},
                timeout=60,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            code = (
                ErrorCode.PROVIDER_RATE_LIMIT
                if exc.response.status_code in (429, 401)
                else ErrorCode.PROVIDER_UNAVAILABLE
            )
            raise AppError(
                f"Replicate error {exc.response.status_code}: {exc.response.text[:200]}", code=code
            ) from exc
        except httpx.HTTPError as exc:
            raise AppError(f"Replicate network error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc

        prediction = resp.json()
        poll_url = (prediction.get("urls") or {}).get("get") or f"{_BASE}/predictions/{prediction.get('id')}"
        data = self._poll(poll_url)

        output = data.get("output")
        if isinstance(output, list):
            output = output[0] if output else None
        if not output or not isinstance(output, str):
            raise AppError("Replicate returned no video output", code=ErrorCode.PROVIDER_BAD_RESPONSE)

        self._download(output, out_path)

        predict_time = float((data.get("metrics") or {}).get("predict_time") or duration_sec)
        return ImageResult(
            path=out_path,
            width=0,
            height=0,
            license="replicate-generated",
            attribution="",
            usage=Usage(
                provider="replicate",
                model=self._model,
                operation="video_clip",
                seconds=predict_time,
                est_cost_usd=video_clip_cost("replicate", predict_time),
            ),
        )

    def _poll(self, poll_url: str) -> dict:
        deadline = time.monotonic() + _POLL_TIMEOUT_SEC
        while True:
            try:
                resp = httpx.get(poll_url, headers=self._headers(), timeout=30)
                resp.raise_for_status()
            except httpx.HTTPError as exc:
                raise AppError(f"Replicate poll error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc
            data = resp.json()
            status = data.get("status")
            if status == "succeeded":
                return data
            if status in ("failed", "canceled"):
                raise AppError(
                    f"Replicate video generation {status}: {data.get('error') or 'no details'}",
                    code=ErrorCode.PROVIDER_UNAVAILABLE,
                )
            if time.monotonic() > deadline:
                raise AppError("Replicate video generation timed out", code=ErrorCode.PROVIDER_UNAVAILABLE)
            time.sleep(_POLL_INTERVAL_SEC)

    def _download(self, url: str, out_path: str) -> None:
        try:
            with httpx.stream("GET", url, timeout=120) as resp:
                resp.raise_for_status()
                with open(out_path, "wb") as fh:
                    for chunk in resp.iter_bytes():
                        fh.write(chunk)
        except httpx.HTTPError as exc:
            raise AppError(f"Replicate download error: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc
