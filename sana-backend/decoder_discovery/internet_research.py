from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.parse import quote_plus, urlencode, urlparse
from urllib.request import Request, urlopen


_USER_AGENT = "SANA-Decoder-Discovery/1.0 (+https://github.com/IrajAzarvand/SANA)"
_TIMEOUT_SECONDS = 12
_MAX_RESULTS_PER_PROVIDER = 5


class _DuckDuckGoResultsParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.results = []
        self._current = None
        self._capture = None
        self._text_parts = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = set((attrs.get("class") or "").split())
        if tag == "a" and "result__a" in classes:
            self._current = {
                "title": "",
                "url": attrs.get("href", ""),
                "snippet": "",
                "provider": "DuckDuckGo",
            }
            self._capture = "title"
            self._text_parts = []
        elif self._current is not None and tag in {"a", "div", "span"} and (
            "result__snippet" in classes
        ):
            self._capture = "snippet"
            self._text_parts = []

    def handle_data(self, data):
        if self._current is not None and self._capture:
            self._text_parts.append(data)

    def handle_endtag(self, tag):
        if self._current is None:
            return
        if self._capture == "title" and tag == "a":
            self._current["title"] = " ".join("".join(self._text_parts).split())
            self._capture = None
            self._text_parts = []
        elif self._capture == "snippet" and tag in {"a", "div", "span"}:
            snippet = " ".join("".join(self._text_parts).split())
            if snippet:
                self._current["snippet"] = snippet
            self._capture = None
            self._text_parts = []
        if tag == "div" and self._current.get("title") and self._current.get("url"):
            self.results.append(self._current)
            self._current = None
            self._capture = None
            self._text_parts = []


def build_research_queries(report: dict) -> list[str]:
    """Create search queries from a complete real session report, without sending raw packets."""
    features = report.get("features", {})
    evidence = report.get("protocol_evidence", {})
    hints = set(report.get("protocol_hints", []))
    message_ids = sorted({
        item.get("message_id", "")
        for item in evidence.get("jt808_frame_evidence", [])
        if item.get("message_id")
    })
    strings = report.get("evidence_strings", [])
    queries = []

    marker_terms = []
    for value in strings:
        # Search only distinctive printable clues, never device identifiers or whole payloads.
        normalized = value.strip()
        if re.search(r"(?i)open[_ -]?jt808", normalized):
            marker_terms.append("OPEN_JT808")
        elif re.search(r"[A-Za-z]{3,}[_-][A-Za-z0-9_-]{3,}", normalized):
            marker_terms.append(normalized[:48])
    for marker in dict.fromkeys(marker_terms):
        queries.append(f'GPS tracker protocol decoder "{marker}"')

    if "jt808_like_framing" in hints and message_ids:
        queries.append(
            "JT/T 808 open source decoder protocol message "
            + " ".join(message_ids[:6])
        )

    prefix = features.get("prefix_hex", "")
    if prefix:
        # A short packet signature is useful for documentation/code search; no full payload is sent.
        queries.append(f'GPS tracker binary protocol decoder hex "{prefix[:24]}"')

    if not queries:
        queries.append("open source GPS tracker binary protocol decoder identify packet format")

    return list(dict.fromkeys(queries))[:4]


def _search_duckduckgo(query: str) -> list[dict]:
    url = "https://html.duckduckgo.com/html/?" + urlencode({"q": query})
    request = Request(url, headers={"User-Agent": _USER_AGENT})
    with urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        html = response.read(2_000_000).decode("utf-8", errors="replace")
    parser = _DuckDuckGoResultsParser()
    parser.feed(html)
    results = []
    for item in parser.results:
        if not item.get("title") or not item.get("url"):
            continue
        if item["url"].startswith("//"):
            item["url"] = "https:" + item["url"]
        results.append(item)
        if len(results) >= _MAX_RESULTS_PER_PROVIDER:
            break
    return results


def _search_github_repositories(query: str) -> list[dict]:
    # GitHub repository search is a public API and does not require code-search authentication.
    url = "https://api.github.com/search/repositories?" + urlencode({
        "q": query,
        "sort": "stars",
        "order": "desc",
        "per_page": _MAX_RESULTS_PER_PROVIDER,
    })
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": _USER_AGENT,
        },
    )
    with urlopen(request, timeout=_TIMEOUT_SECONDS) as response:
        payload = json.loads(response.read(1_000_000).decode("utf-8"))
    return [
        {
            "title": item.get("full_name", ""),
            "url": item.get("html_url", ""),
            "snippet": (item.get("description") or "")[:500],
            "provider": "GitHub",
            "stars": item.get("stargazers_count", 0),
            "language": item.get("language") or "",
            "license": (item.get("license") or {}).get("spdx_id") or "unknown",
        }
        for item in payload.get("items", [])[:_MAX_RESULTS_PER_PROVIDER]
    ]


def search_protocol_references(queries: list[str]) -> dict:
    """Search public web and GitHub; report failures without changing database state."""
    all_results = []
    errors = []
    seen_urls = set()

    for query in queries:
        for provider, search_fn in (
            ("DuckDuckGo", _search_duckduckgo),
            ("GitHub", _search_github_repositories),
        ):
            try:
                results = search_fn(query)
                for result in results:
                    url = result.get("url", "")
                    if url and url not in seen_urls:
                        seen_urls.add(url)
                        result["matched_query"] = query
                        all_results.append(result)
            except (HTTPError, URLError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
                errors.append({
                    "provider": provider,
                    "query": query,
                    "error": f"{type(exc).__name__}: {str(exc)[:240]}",
                })
            except Exception as exc:
                errors.append({
                    "provider": provider,
                    "query": query,
                    "error": f"{type(exc).__name__}: {str(exc)[:240]}",
                })

    return {
        "queries": queries,
        "results": all_results,
        "errors": errors,
        "raw_payload_uploaded": False,
    }
