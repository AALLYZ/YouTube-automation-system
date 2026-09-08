"""Deep provider self-checks for `GET /api/health/deep`.

Stub providers are exercised for real (cheap, offline). Real providers are only
*constructed* — that already validates configuration (missing keys raise
``CONFIG``) — never called, so the check costs nothing and hits no network.
"""
from __future__ import annotations

import os
import tempfile

from app.core.config import settings
from app.core.logging import get_logger
from app.providers import registry

log = get_logger("providers.health")


def _probe_storage(p) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        src = os.path.join(tmp, "probe.txt")
        with open(src, "w") as fh:
            fh.write("ok")
        key = "healthcheck/probe.txt"
        p.put(src, key)
        if not p.exists(key):
            raise RuntimeError("storage put/exists mismatch")
        dst = os.path.join(tmp, "back.txt")
        p.get(key, dst)
        if open(dst).read() != "ok":
            raise RuntimeError("storage round-trip corrupted")
    return "round-trip ok"


def _probe_ai(p) -> str:
    if p.name != "stub":
        return "configured (not exercised)"
    res = p.complete(system="", prompt="ping", task="", max_tokens=16)
    return f"completion {len(res.text)} chars"


def _probe_research(p) -> str:
    if p.name != "stub":
        return "configured (not exercised)"
    sources, _ = p.search("ping", max_sources=1)
    return f"{len(sources)} source(s)"


def _probe_voice(p) -> str:
    if p.name != "stub":
        return "configured (not exercised)"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "v.wav")
        r = p.synthesize(text="hello there", out_path=out)
        return f"{r.duration_sec:.1f}s wav"


def _probe_image(p) -> str:
    if p.name != "stub":
        return "configured (not exercised)"
    with tempfile.TemporaryDirectory() as tmp:
        out = os.path.join(tmp, "i.png")
        r = p.generate(prompt="a circle", out_path=out, width=64, height=64)
        return f"{r.width}x{r.height} png"


def _probe_stock(p) -> str:
    if p.name != "stub":
        return "configured (not exercised)"
    with tempfile.TemporaryDirectory() as tmp:
        res = p.search("nature", out_path=os.path.join(tmp, "s.jpg"))
    return "hit" if res else "no result (ok)"


def _probe_video_clip(p) -> str:
    return "configured" if p.name != "stub" else "stub ready"


def _probe_youtube(p) -> str:
    return "configured (not exercised)" if p.name != "stub" else "stub ready"


def _probe_notifier(p) -> str:
    if p.name in ("console", "stub"):
        p.send(recipient="healthcheck", body="probe")
        return "send ok"
    return "configured (not exercised)"


_CHECKS = [
    ("storage", registry.get_storage, _probe_storage),
    ("ai", registry.get_ai, _probe_ai),
    ("research", registry.get_research, _probe_research),
    ("voice", registry.get_voice, _probe_voice),
    ("image", registry.get_image, _probe_image),
    ("stock", registry.get_stock, _probe_stock),
    ("video_clip", registry.get_video_clip, _probe_video_clip),
    ("youtube", registry.get_youtube, _probe_youtube),
    ("notifier", registry.get_notifier, _probe_notifier),
]


def deep_check() -> dict:
    out: dict[str, dict] = {}
    for name, getter, probe in _CHECKS:
        configured = getattr(settings, f"{name}_provider", "?")
        try:
            provider = getter()
            out[name] = {"ok": True, "provider": provider.name, "detail": probe(provider)}
        except Exception as exc:  # noqa: BLE001
            out[name] = {"ok": False, "provider": configured, "error": str(exc)[:300]}
            log.warning("deep check failed for %s: %s", name, exc)
    return out
