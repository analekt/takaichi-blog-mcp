"""Tests for the retry/backoff and fetch-orchestration paths.

These use a fake httpx client so no real network traffic occurs, and patch
backoff sleeps to zero so tests run instantly. They cover the riskiest logic:
transient-error retries and per-article fetch error handling.
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from takaichi_blog_mcp import config, fetch, store, wayback

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch):
    """Make retry backoff and the inter-request delay instantaneous."""
    monkeypatch.setattr(config, "RETRY_BACKOFF_SECONDS", (0, 0, 0))

    async def _instant(_seconds):
        return None

    monkeypatch.setattr(wayback.asyncio, "sleep", _instant)


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(config.DATA_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


class FakeClient:
    """Minimal stand-in for httpx.AsyncClient returning queued responses."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    async def get(self, url, params=None):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _response(status: int, *, text: str = "", json_body=None) -> httpx.Response:
    request = httpx.Request("GET", "https://web.archive.org/x")
    if json_body is not None:
        return httpx.Response(status, json=json_body, request=request)
    return httpx.Response(status, text=text, request=request)


async def test_retry_succeeds_after_transient_503() -> None:
    client = FakeClient([_response(503), _response(200, text="ok")])
    resp = await wayback._request_with_retry(client, "https://x")
    assert resp.status_code == 200
    assert client.calls == 2  # one retry


async def test_retry_gives_up_after_max_retries() -> None:
    client = FakeClient([_response(503)] * (config.MAX_RETRIES + 1))
    with pytest.raises(httpx.HTTPStatusError):
        await wayback._request_with_retry(client, "https://x")
    assert client.calls == config.MAX_RETRIES + 1


async def test_fetch_cdx_index_reduces_rows() -> None:
    rows = [
        ["original", "timestamp"],
        ["https://www.sanae.gr.jp/column_detail8.html", "20220101000000"],
        ["https://www.sanae.gr.jp/column_detail8.html", "20251021182115"],
        ["https://www.sanae.gr.jp/column_detail.html?id=120", "20210101000000"],
    ]
    client = FakeClient([_response(200, json_body=rows)])
    records = await wayback.fetch_cdx_index(client)
    assert [r["id"] for r in records] == [8]
    assert records[0]["latest_timestamp"] == "20251021182115"


async def test_fetch_one_saves_on_success(data_dir) -> None:
    html = (FIXTURES / "8.html").read_text(encoding="utf-8")
    record = {
        "id": 8,
        "original_url": "https://www.sanae.gr.jp/column_detail8.html",
        "latest_timestamp": "20251021182115",
        "wayback_url": "https://web.archive.org/web/x/y",
        "snapshot_url": "https://web.archive.org/web/xid_/y",
    }
    client = FakeClient([_response(200, text=html)])
    ok = await fetch._fetch_one(client, record)
    assert ok is True
    saved = store.load_article(8)
    assert saved is not None
    assert saved["title"] == "ようやく臨時国会が召集されました。"


async def test_fetch_one_returns_false_on_parse_error(data_dir) -> None:
    record = {
        "id": 999,
        "original_url": "https://www.sanae.gr.jp/column_detail999.html",
        "latest_timestamp": "20250101000000",
        "wayback_url": "x",
        "snapshot_url": "y",
    }
    client = FakeClient([_response(200, text="<html><body>no article</body></html>")])
    ok = await fetch._fetch_one(client, record)
    assert ok is False
    assert store.load_article(999) is None


async def test_fetch_one_returns_false_on_network_error(data_dir) -> None:
    record = {
        "id": 5,
        "original_url": "https://www.sanae.gr.jp/column_detail5.html",
        "latest_timestamp": "20250101000000",
        "wayback_url": "x",
        "snapshot_url": "y",
    }
    err = httpx.ConnectError("boom")
    client = FakeClient([err] * (config.MAX_RETRIES + 1))
    ok = await fetch._fetch_one(client, record)
    assert ok is False
