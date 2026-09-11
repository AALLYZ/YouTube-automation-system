"""Provider interfaces. Concrete adapters live in sibling packages.

Every interface has a `stub` implementation so the whole pipeline runs offline.
"""
from __future__ import annotations

import abc
import dataclasses
from typing import Any, Optional


# ---------------- DTOs ----------------
@dataclasses.dataclass
class Usage:
    provider: str
    model: Optional[str] = None
    operation: str = ""
    input_tokens: int = 0
    output_tokens: int = 0
    units: int = 0
    seconds: float = 0.0
    est_cost_usd: float = 0.0


@dataclasses.dataclass
class AIResult:
    text: str
    usage: Usage


@dataclasses.dataclass
class Source:
    source: str
    url: str
    title: str
    key_facts: list[str]
    date: Optional[str] = None
    relevance: float = 0.0
    confidence: float = 0.0


@dataclasses.dataclass
class VoiceResult:
    audio_path: str
    duration_sec: float
    timestamps: list[dict[str, Any]]
    usage: Usage


@dataclasses.dataclass
class ImageResult:
    path: str
    width: int
    height: int
    license: str
    attribution: str
    usage: Usage


@dataclasses.dataclass
class StockResult:
    path: str
    width: int
    height: int
    license: str
    attribution: str
    is_video: bool = False


@dataclasses.dataclass
class UploadResult:
    video_id: str
    url: str
    status: str
    quota_units: int = 0


@dataclasses.dataclass
class TrendingVideo:
    video_id: str
    title: str
    description: str
    channel_title: str
    tags: list[str]
    category_id: str
    view_count: int
    published_at: str
    url: str
    thumbnail_url: str = ""


@dataclasses.dataclass
class NotifyResult:
    message_id: str
    status: str


# ---------------- Interfaces ----------------
class AIProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def complete(
        self,
        *,
        system: str,
        prompt: str,
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2000,
        json_mode: bool = False,
        task: str = "",
    ) -> AIResult:
        """Return a completion.

        `task` is a semantic hint (e.g. "topics", "script", "script_qa") that
        real providers may ignore but stubs use to return the right shape.
        """
        ...


class ResearchProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def search(self, query: str, *, depth: str = "basic", max_sources: int = 5) -> tuple[list[Source], Usage]: ...


class VoiceProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def synthesize(
        self,
        *,
        text: str,
        out_path: str,
        voice: str = "",
        language: str = "English",
        speed: float = 1.0,
        emotion: str = "neutral",
    ) -> VoiceResult: ...


class ImageProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def generate(
        self, *, prompt: str, out_path: str, width: int = 1920, height: int = 1080, style: str = ""
    ) -> ImageResult: ...


class VideoClipProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def generate(self, *, prompt: str, out_path: str, duration_sec: float = 4.0) -> ImageResult: ...


class StockMediaProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def search(self, query: str, *, kind: str = "photo", out_path: str = "") -> Optional[StockResult]: ...


class StorageProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def put(self, local_path: str, key: str) -> str: ...

    @abc.abstractmethod
    def get(self, key: str, local_path: str) -> str: ...

    @abc.abstractmethod
    def open_path(self, key: str) -> str:
        """Return a local filesystem path for the key (download if needed)."""

    @abc.abstractmethod
    def url(self, key: str) -> str: ...

    @abc.abstractmethod
    def exists(self, key: str) -> bool: ...

    def delete(self, key: str) -> None:
        """Delete one object. Best-effort; missing key is not an error."""
        raise NotImplementedError

    def delete_prefix(self, prefix: str) -> int:
        """Delete every object under a key prefix. Returns count removed."""
        raise NotImplementedError


class YouTubeProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def upload(
        self,
        *,
        video_path: str,
        title: str,
        description: str,
        tags: list[str],
        category_id: str,
        privacy_status: str,
        publish_at: Optional[str] = None,
        credential: Optional[dict[str, Any]] = None,
    ) -> UploadResult: ...

    @abc.abstractmethod
    def set_thumbnail(self, *, video_id: str, image_path: str, credential: Optional[dict[str, Any]] = None) -> int: ...

    def add_to_playlist(
        self, *, video_id: str, playlist_id: str, credential: Optional[dict[str, Any]] = None
    ) -> int:
        """Add an uploaded video to a playlist. Returns quota units consumed."""
        return 0

    def list_trending(
        self,
        *,
        region_code: str = "US",
        category_id: Optional[str] = None,
        max_results: int = 15,
        credential: Optional[dict[str, Any]] = None,
    ) -> tuple[list["TrendingVideo"], int]:
        """Return the current trending (most-popular) videos plus quota units consumed."""
        raise NotImplementedError


class NotifierProvider(abc.ABC):
    name: str = "base"

    @abc.abstractmethod
    def send(self, *, recipient: str, body: str) -> NotifyResult: ...
