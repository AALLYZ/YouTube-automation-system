from __future__ import annotations

from typing import Optional

from app.providers.base import StockMediaProvider, StockResult
from app.providers.image.stub import StubImage


class StubStock(StockMediaProvider):
    """No real stock catalogue offline — falls back to a generated card."""

    name = "stub"

    def search(self, query: str, *, kind: str = "photo", out_path: str = "") -> Optional[StockResult]:
        if not out_path:
            return None
        res = StubImage().generate(prompt=f"stock: {query}", out_path=out_path)
        return StockResult(
            path=out_path,
            width=res.width,
            height=res.height,
            license="generated-stub",
            attribution="",
            is_video=False,
        )
