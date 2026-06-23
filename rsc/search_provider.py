from __future__ import annotations

import json
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol
from urllib import parse, request

from .retry import retry_call

_STRIP_TAGS = (
    "img",
    "video",
    "audio",
    "picture",
    "iframe",
    "embed",
    "object",
    "script",
    "style",
)
_STRIP_TAG_PATTERN = re.compile(
    r"<(?P<tag>" + "|".join(_STRIP_TAGS) + r")\b[^>]*>.*?</(?P=tag)>",
    re.IGNORECASE | re.DOTALL,
)
_STRIP_SELF_CLOSING_PATTERN = re.compile(
    r"<(?:" + "|".join(_STRIP_TAGS) + r")\b[^>]*/?>",
    re.IGNORECASE,
)
_STRIP_MARKDOWN_IMAGE_PATTERN = re.compile(r"!\[[^\]]*\]\([^)]*\)")


def strip_unwanted_media_tags(markdown: str) -> str:
    """Remove HTML media/embed tags and markdown image links from search content."""
    cleaned = _STRIP_TAG_PATTERN.sub("", markdown)
    cleaned = _STRIP_SELF_CLOSING_PATTERN.sub("", cleaned)
    cleaned = _STRIP_MARKDOWN_IMAGE_PATTERN.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


# Regex to match fenced code block markers (opening or closing), with or
# without a language identifier. Matches lines that contain only ``` with
# optional leading/trailing whitespace and an optional language tag.
_FENCED_CODE_MARKER = re.compile(r"^[ \t]*`{3,}[^\n]*$", re.MULTILINE)

# Minimum number of contiguous sentences a block must contain to be kept,
# unless it contains structured content (bullets, headings, tables).
_MIN_SENTENCES = 3

# A sentence ends with .!? followed by whitespace or end-of-string.
_SENTENCE_PATTERN = re.compile(r"[.!?](?:\s|$)")


def filter_prose_blocks(markdown: str) -> str:
    """Keep only blocks that contain structured content or ≥3 contiguous sentences.

    A block is a paragraph separated by blank lines (``\\n\\n``). Structured
    content means bullet lists (``- ``, ``* ``, ``+ ``), headings (``#``),
    or tables (``|``). A sentence is a run of text ending in ``.``, ``!``,
    or ``?`` followed by whitespace or end-of-string. Fragments shorter than
    10 characters are not counted as sentences.

    Fenced code block markers (````` ```) are stripped, but the content
    between them is kept and evaluated by the same rules.

    This filters out navigation labels, menu items, cookie banners, user
    comments, footers, and other non-prose fragments from Firecrawl search
    results without losing meaningful content.
    """
    if not markdown.strip():
        return ""
    # Step 1: Strip fenced code block markers, keep content inside.
    cleaned = _FENCED_CODE_MARKER.sub("", markdown)
    # Step 2: Split into blocks on blank lines.
    blocks = re.split(r"\n{2,}", cleaned)
    kept: list[str] = []
    for block in blocks:
        stripped = block.strip()
        if not stripped:
            continue
        if _has_structured_content(stripped):
            kept.append(stripped)
            continue
        if _count_sentences(stripped) >= _MIN_SENTENCES:
            kept.append(stripped)
    return "\n\n".join(kept)


def _has_structured_content(block: str) -> bool:
    """Return True if the block contains bullets, headings, or tables."""
    for line in block.splitlines():
        line_stripped = line.strip()
        if not line_stripped:
            continue
        # Bullet lists
        if line_stripped.startswith(("- ", "* ", "+ ")):
            return True
        # Headings
        if line_stripped.startswith("#"):
            return True
        # Tables
        if "|" in line_stripped:
            return True
    return False


def _count_sentences(block: str) -> int:
    """Count sentences in a block. Fragments <10 chars are not counted."""
    count = 0
    for line in block.splitlines():
        stripped = line.strip()
        if len(stripped) < 10:
            continue
        count += len(_SENTENCE_PATTERN.findall(stripped))
    return count


class SearchProviderError(RuntimeError):
    """Raised when a configured search provider cannot return markdown."""


class RequestConcurrencyLimiter:
    def __init__(self, max_concurrency: int) -> None:
        if not 1 <= max_concurrency <= 50:
            raise SearchProviderError("max_concurrency must be in [1, 50]")
        self.max_concurrency = max_concurrency
        self._semaphore = threading.BoundedSemaphore(max_concurrency)

    def __enter__(self) -> "RequestConcurrencyLimiter":
        self._semaphore.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback) -> bool:
        self._semaphore.release()
        return False


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, *, max_results: int = 5) -> str:
        """Return markdown-structured search context for the query."""


@dataclass(frozen=True)
class FunctionSearchProvider:
    search_func: Callable[[str, int], str]
    name: str = "function"

    def search(self, query: str, *, max_results: int = 5) -> str:
        result = self.search_func(query, max_results)
        if not isinstance(result, str):
            raise SearchProviderError("Search function must return markdown as str")
        return result


@dataclass(frozen=True)
class HTTPMarkdownSearchProvider:
    endpoint: str
    name: str = "http"
    method: str = "POST"
    timeout_seconds: float = 30.0
    headers: dict[str, str] = field(default_factory=dict)
    query_param: str = "query"
    max_results_param: str = "max_results"
    max_concurrency: int = 2
    _request_limiter: RequestConcurrencyLimiter = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_request_limiter",
            RequestConcurrencyLimiter(self.max_concurrency),
        )

    def search(self, query: str, *, max_results: int = 5) -> str:
        method = self.method.upper()
        if method == "GET":
            return self._get(query, max_results)
        if method == "POST":
            return self._post(query, max_results)
        raise SearchProviderError(f"Unsupported search HTTP method: {self.method}")

    def _get(self, query: str, max_results: int) -> str:
        params = parse.urlencode(
            {self.query_param: query, self.max_results_param: str(max_results)}
        )
        separator = "&" if "?" in self.endpoint else "?"
        url = f"{self.endpoint}{separator}{params}"
        req = request.Request(url, headers=self.headers, method="GET")
        return self._read_markdown(req)

    def _post(self, query: str, max_results: int) -> str:
        payload = json.dumps(
            {self.query_param: query, self.max_results_param: max_results}
        ).encode("utf-8")
        headers = {"Content-Type": "application/json", **self.headers}
        req = request.Request(
            self.endpoint, data=payload, headers=headers, method="POST"
        )
        return self._read_markdown(req)

    def _read_markdown(self, req: request.Request) -> str:
        try:
            with self._request_limiter:
                body = retry_call(
                    lambda: _urlopen_text(req, self.timeout_seconds),
                )
        except OSError as exc:
            raise SearchProviderError(f"Search request failed: {exc}") from exc
        if not body.strip():
            raise SearchProviderError("Search provider returned empty markdown")
        return filter_prose_blocks(strip_unwanted_media_tags(body))


# ---------------------------------------------------------------------------
# Link stripping for Firecrawl content
# ---------------------------------------------------------------------------

# Matches markdown links [text](url) — keeps the text, drops the URL.
_MD_LINK_PATTERN = re.compile(r"\[([^\]]*)\]\([^)]*\)")

# Matches bare URLs (http/https).
_BARE_URL_PATTERN = re.compile(r"https?://[^\s)>\]]+")

# Matches "URL: ..." lines.
_URL_LINE_PATTERN = re.compile(r"(?m)^URL:\s*.*$")


def _strip_links(text: str) -> str:
    """Remove all links from text while preserving readable content."""
    text = _MD_LINK_PATTERN.sub(r"\1", text)
    text = _URL_LINE_PATTERN.sub("", text)
    text = _BARE_URL_PATTERN.sub("", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


@dataclass(frozen=True)
class FirecrawlSearchProvider:
    api_key: str | None = None
    endpoint: str = "https://api.firecrawl.dev/v2/search"
    name: str = "firecrawl"
    timeout_seconds: float = 30.0
    sources: tuple[str, ...] = ("web",)
    categories: tuple[str, ...] = ()
    max_age_ms: int = 172800000
    only_main_content: bool = True
    max_concurrency: int = 2
    _request_limiter: RequestConcurrencyLimiter = field(
        init=False, repr=False, compare=False
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_request_limiter",
            RequestConcurrencyLimiter(self.max_concurrency),
        )

    def search(self, query: str, *, max_results: int = 5) -> str:
        payload = {
            "query": query,
            "sources": list(self.sources),
            "categories": list(self.categories),
            "limit": max_results,
            "scrapeOptions": {
                "onlyMainContent": self.only_main_content,
                "maxAge": self.max_age_ms,
                "parsers": [],
                "formats": ["markdown"],
                "excludeTags": [
                    "img",
                    "video",
                    "audio",
                    "picture",
                    "iframe",
                    "embed",
                    "object",
                    "script",
                    "style",
                ],
            },
        }
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = request.Request(
            self.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with self._request_limiter:
                body = retry_call(
                    lambda: _urlopen_text(req, self.timeout_seconds),
                )
        except OSError as exc:
            raise SearchProviderError(f"Firecrawl search failed: {exc}") from exc
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError as exc:
            raise SearchProviderError("Firecrawl returned non-JSON response") from exc
        return self._format_response(query, parsed)

    def _format_response(self, query: str, payload: dict) -> str:
        if payload.get("success") is False:
            raise SearchProviderError(f"Firecrawl search failed: {payload}")
        data = payload.get("data", {})
        sections = [f"# Web Search Results\n\nQuery: {query}"]
        if isinstance(data, list):
            self._append_result_list(sections, "web", data)
        elif isinstance(data, dict):
            for source in ("web", "news", "images"):
                items = data.get(source) or []
                if items:
                    self._append_result_list(sections, source, items)
        else:
            raise SearchProviderError(
                "Firecrawl response data must be a list or object"
            )
        if len(sections) == 1:
            sections.append("No results returned.")
        return "\n\n".join(sections)

    @staticmethod
    def _append_result_list(
        sections: list[str], source: str, items: list[dict]
    ) -> None:
        sections.append(f"## {source.title()} Results")
        for item in items:
            title = _strip_links(
                item.get("title")
                or item.get("url")
                or item.get("imageUrl")
                or "Untitled"
            )
            description = _strip_links(
                item.get("description") or item.get("snippet") or ""
            )
            position = item.get("position")
            heading = (
                f"### {position}. {title}" if position is not None else f"### {title}"
            )
            result_parts = [heading]
            if description:
                result_parts.append(description)
            markdown = item.get("markdown")
            if markdown:
                result_parts.append(
                    _strip_links(
                        filter_prose_blocks(strip_unwanted_media_tags(markdown))
                    )
                )
            sections.append("\n\n".join(result_parts))


def _urlopen_text(req: request.Request, timeout_seconds: float) -> str:
    with request.urlopen(req, timeout=timeout_seconds) as response:
        return response.read().decode("utf-8")
