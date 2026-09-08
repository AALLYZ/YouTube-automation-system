from __future__ import annotations

import hashlib

from app.providers.base import ResearchProvider, Source, Usage


class StubResearch(ResearchProvider):
    name = "stub"

    def search(self, query: str, *, depth: str = "basic", max_sources: int = 5):
        s = int(hashlib.sha256(query.encode()).hexdigest(), 16)
        n = min(max_sources, 3 + s % 3)
        sources = [
            Source(
                source=f"example-source-{i + 1}.org",
                url=f"https://example-source-{i + 1}.org/{abs(hash(query)) % 9999}",
                title=f"{query.strip().title()} — reference {i + 1}",
                key_facts=[
                    f"Fact {i + 1}a about {query.strip()}.",
                    f"Fact {i + 1}b about {query.strip()}.",
                ],
                date="2024-01-01",
                relevance=round(0.9 - i * 0.1, 2),
                confidence=round(0.8 - i * 0.05, 2),
            )
            for i in range(n)
        ]
        return sources, Usage(provider="stub", operation="search", units=1)
