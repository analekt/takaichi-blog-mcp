"""Wayback Machine access: CDX listing + archived snapshot fetching.

The pure selection logic (parsing CDX rows -> latest snapshot per article) is
separated from network I/O so it can be unit-tested offline. Network calls are
thin async wrappers with polite rate limiting and exponential-backoff retries.

CDX query strategy (verified empirically):

    url=sanae.gr.jp/column_detail & matchType=prefix
    filter=statuscode:200 & fl=original,timestamp & output=json

This returns every captured snapshot of both URL families
(``column_detail{id}.html`` and ``column_detail.html?id={id}``). We keep only
the numbered ``column_detail{id}.html`` family and, for each article id, the
snapshot with the greatest (latest) timestamp.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional

import httpx

from . import config

_ARTICLE_URL_RE = re.compile(r"/column_detail(\d+)\.html$")


def snapshot_url(timestamp: str, original_url: str) -> str:
    """Build the raw (un-rewritten) Wayback snapshot URL for an article."""
    return config.SNAPSHOT_URL_TEMPLATE.format(timestamp=timestamp, url=original_url)


def _wayback_view_url(timestamp: str, original_url: str) -> str:
    """Human-facing Wayback URL (with toolbar) for citations."""
    return f"https://web.archive.org/web/{timestamp}/{original_url}"


def select_latest_per_article(rows: List[List[str]]) -> List[Dict[str, Any]]:
    """Reduce raw CDX rows to one latest-snapshot record per article.

    Args:
        rows: CDX ``output=json`` rows. The first row is a header
            (``["original", "timestamp"]``); remaining rows are data.

    Returns:
        List of dicts (sorted by id) with keys ``id``, ``original_url``,
        ``latest_timestamp``, ``wayback_url``, ``snapshot_url``.
    """
    if not rows:
        return []

    data_rows = rows[1:] if rows and rows[0][:1] == ["original"] else rows

    latest: Dict[int, Dict[str, str]] = {}
    for row in data_rows:
        if len(row) < 2:
            continue
        original, timestamp = row[0], row[1]
        match = _ARTICLE_URL_RE.search(original)
        if not match:
            continue
        article_id = int(match.group(1))
        current = latest.get(article_id)
        if current is None or timestamp > current["timestamp"]:
            latest[article_id] = {"original": original, "timestamp": timestamp}

    result: List[Dict[str, Any]] = []
    for article_id in sorted(latest):
        original = latest[article_id]["original"]
        timestamp = latest[article_id]["timestamp"]
        result.append(
            {
                "id": article_id,
                "original_url": original,
                "latest_timestamp": timestamp,
                "wayback_url": _wayback_view_url(timestamp, original),
                "snapshot_url": snapshot_url(timestamp, original),
            }
        )
    return result


async def _request_with_retry(
    client: httpx.AsyncClient,
    url: str,
    *,
    params: Optional[dict] = None,
) -> httpx.Response:
    """GET ``url`` with exponential-backoff retry on 429/503 and timeouts."""
    last_exc: Optional[Exception] = None
    for attempt in range(config.MAX_RETRIES + 1):
        try:
            response = await client.get(url, params=params)
            if response.status_code in (429, 503):
                raise httpx.HTTPStatusError(
                    f"Transient {response.status_code}",
                    request=response.request,
                    response=response,
                )
            response.raise_for_status()
            return response
        except (httpx.HTTPStatusError, httpx.TransportError) as exc:
            last_exc = exc
            if attempt >= config.MAX_RETRIES:
                break
            backoff = config.RETRY_BACKOFF_SECONDS[
                min(attempt, len(config.RETRY_BACKOFF_SECONDS) - 1)
            ]
            await asyncio.sleep(backoff)
    assert last_exc is not None
    raise last_exc


async def fetch_cdx_index(client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """Fetch and reduce the CDX listing to latest-snapshot-per-article records."""
    response = await _request_with_retry(
        client,
        config.CDX_API_URL,
        params={
            "url": "sanae.gr.jp/column_detail",
            "matchType": "prefix",
            "filter": "statuscode:200",
            "fl": "original,timestamp",
            "output": "json",
        },
    )
    rows = response.json()
    return select_latest_per_article(rows)


async def fetch_snapshot_html(client: httpx.AsyncClient, record: Dict[str, Any]) -> str:
    """Fetch the raw archived HTML for a single article record."""
    response = await _request_with_retry(client, record["snapshot_url"])
    response.encoding = response.encoding or "utf-8"
    return response.text


def make_client() -> httpx.AsyncClient:
    """Construct a configured async HTTP client for Wayback requests."""
    return httpx.AsyncClient(
        timeout=config.REQUEST_TIMEOUT_SECONDS,
        headers={"User-Agent": config.USER_AGENT},
        follow_redirects=True,
    )
