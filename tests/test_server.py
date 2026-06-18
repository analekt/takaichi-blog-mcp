"""Tests for the MCP tool functions (called directly, not over transport)."""

from __future__ import annotations

import json

import pytest

from takaichi_blog_mcp import config, server, store


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(config.DATA_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


def _seed(article_id: int, **overrides) -> None:
    base = {
        "id": article_id,
        "title": f"記事{article_id}について",
        "category": "9期目の永田町から",
        "published_date": f"2023-03-{article_id:02d}",
        "date_source": "html",
        "archived_date": "2025-01-01",
        "original_url": f"https://www.sanae.gr.jp/column_detail{article_id}.html",
        "wayback_url": f"https://web.archive.org/web/x/...{article_id}",
        "content_markdown": f"本文{article_id}です。安全保障について述べます。",
    }
    base.update(overrides)
    store.save_article(base)


async def test_tools_report_not_provisioned(data_dir) -> None:
    out = await server.takaichi_list_articles(server.ListArticlesInput())
    assert "takaichi-blog-fetch" in out
    out = await server.takaichi_list_categories()
    assert "takaichi-blog-fetch" in out
    out = await server.takaichi_get_article(server.GetArticleInput(id=8))
    assert "takaichi-blog-fetch" in out
    out = await server.takaichi_search_articles(server.SearchArticlesInput(query="x"))
    assert "takaichi-blog-fetch" in out


async def test_list_articles_returns_metadata(data_dir) -> None:
    _seed(1)
    _seed(2)
    store.rebuild_index()
    out = json.loads(await server.takaichi_list_articles(server.ListArticlesInput()))
    assert out["total"] == 2
    assert out["count"] == 2
    assert "content_markdown" not in out["articles"][0]


async def test_get_article_returns_full_body(data_dir) -> None:
    _seed(8)
    store.rebuild_index()
    out = json.loads(await server.takaichi_get_article(server.GetArticleInput(id=8)))
    assert out["id"] == 8
    assert "本文8です" in out["content_markdown"]
    assert out["wayback_url"].endswith("8")


async def test_get_unknown_article_errors(data_dir) -> None:
    _seed(1)
    store.rebuild_index()
    out = await server.takaichi_get_article(server.GetArticleInput(id=404))
    assert "not found" in out


async def test_search_returns_excerpts(data_dir) -> None:
    _seed(1)
    _seed(2)
    store.rebuild_index()
    out = json.loads(
        await server.takaichi_search_articles(server.SearchArticlesInput(query="安全保障"))
    )
    assert out["count"] == 2
    assert "安全保障" in out["results"][0]["excerpt"]
    assert "wayback_url" in out["results"][0]


async def test_list_categories_counts(data_dir) -> None:
    _seed(1)
    _seed(2)
    store.rebuild_index()
    out = json.loads(await server.takaichi_list_categories())
    assert out["total_articles"] == 2
    assert out["categories"][0]["count"] == 2
    assert out["categories"][0]["category"] == "9期目の永田町から"
