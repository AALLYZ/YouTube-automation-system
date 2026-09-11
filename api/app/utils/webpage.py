"""Fetch an arbitrary web page and pull out its readable text.

No third-party HTML parser — the stdlib ``html.parser`` is enough to strip
script/style/nav noise and collect visible text plus the ``<title>``. Basic
SSRF guards: only http(s) schemes, and every resolved address (initial host
and, since redirects can retarget it, the final one too) must be a public
address, not a private/loopback/link-local/reserved one.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

from app.core.errors import AppError, ErrorCode

_MAX_BYTES = 3_000_000  # stop reading a response past ~3 MB
_SKIP_TAGS = {"script", "style", "noscript", "header", "footer", "nav", "svg", "form", "aside"}
_UA = "Mozilla/5.0 (compatible; YTAutomationBot/1.0)"


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.chunks: list[str] = []
        self.title_chunks: list[str] = []
        self._skip_depth = 0
        self._in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in _SKIP_TAGS:
            self._skip_depth += 1
        if tag == "title":
            self._in_title = True

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == "title":
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._in_title:
            self.title_chunks.append(data)
            return
        if self._skip_depth:
            return
        text = data.strip()
        if text:
            self.chunks.append(text)


def _assert_public_host(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise AppError(f"Could not resolve host: {host}", code=ErrorCode.VALIDATION) from exc
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast or ip.is_unspecified:
            raise AppError("That URL points to a non-public address", code=ErrorCode.VALIDATION)


def extract_text(html: str) -> tuple[str, str]:
    """Return (title, flattened visible text) for raw HTML. Pure — no I/O."""
    parser = _TextExtractor()
    parser.feed(html)
    text = re.sub(r"\s+", " ", " ".join(parser.chunks)).strip()
    title = re.sub(r"\s+", " ", "".join(parser.title_chunks)).strip()
    return title, text


def fetch_page_text(url: str, *, max_chars: int = 8000) -> dict:
    """Fetch `url` and return {title, text, domain, url}. Raises AppError on failure."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.hostname:
        raise AppError("Only http(s) URLs are supported", code=ErrorCode.VALIDATION)
    _assert_public_host(parsed.hostname)

    try:
        with httpx.Client(follow_redirects=True, timeout=15.0, headers={"User-Agent": _UA}) as client:
            with client.stream("GET", url) as resp:
                if resp.status_code >= 400:
                    raise AppError(
                        f"Fetch failed: HTTP {resp.status_code}", code=ErrorCode.PROVIDER_UNAVAILABLE
                    )
                content_type = resp.headers.get("content-type", "")
                if "html" not in content_type:
                    raise AppError("URL did not return an HTML page", code=ErrorCode.VALIDATION)
                final_host = urlparse(str(resp.url)).hostname
                if final_host and final_host != parsed.hostname:
                    _assert_public_host(final_host)
                body = bytearray()
                for chunk in resp.iter_bytes():
                    body.extend(chunk)
                    if len(body) > _MAX_BYTES:
                        break
                html = body.decode(resp.encoding or "utf-8", errors="ignore")
    except httpx.HTTPError as exc:
        raise AppError(f"Could not fetch URL: {exc}", code=ErrorCode.PROVIDER_UNAVAILABLE) from exc

    title, text = extract_text(html)
    if not text:
        raise AppError("No readable text found on that page", code=ErrorCode.VALIDATION)
    return {
        "title": title[:300] or parsed.hostname,
        "text": text[:max_chars],
        "domain": parsed.hostname,
        "url": url,
    }
