"""Tests for the local data store (read/write of parsed articles + index)."""

from __future__ import annotations

import json

import pytest

from takaichi_blog_mcp import config, store


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv(config.DATA_DIR_ENV_VAR, str(tmp_path))
    return tmp_path


def _sample(article_id: int, **overrides) -> dict:
    base = {
        "id": article_id,
        "title": f"記事{article_id}",
        "category": "テストカテゴリ",
        "published_date": "2020-01-01",
        "date_source": "html",
        "archived_date": "2022-01-01",
        "original_url": f"https://www.sanae.gr.jp/column_detail{article_id}.html",
        "wayback_url": "https://web.archive.org/web/x/y",
        "content_markdown": f"本文 {article_id}",
        "content_html": f"<p>本文 {article_id}</p>",
    }
    base.update(overrides)
    return base


def test_is_provisioned_false_when_empty(data_dir) -> None:
    assert store.is_provisioned() is False


def test_save_and_load_article_roundtrip(data_dir) -> None:
    store.save_article(_sample(42))
    loaded = store.load_article(42)
    assert loaded is not None
    assert loaded["id"] == 42
    assert loaded["content_markdown"] == "本文 42"
    # Markdown file is written too.
    assert config.markdown_path(42).exists()
    assert "本文 42" in config.markdown_path(42).read_text(encoding="utf-8")


def test_content_html_is_not_persisted(data_dir) -> None:
    store.save_article(_sample(7, content_html="<p>should be dropped</p>"))
    loaded = store.load_article(7)
    assert loaded is not None
    assert "content_html" not in loaded
    assert loaded["content_markdown"] == "本文 7"


def test_load_missing_article_returns_none(data_dir) -> None:
    store.save_article(_sample(1))
    assert store.load_article(999) is None


def test_rebuild_and_load_index(data_dir) -> None:
    for i in (3, 1, 2):
        store.save_article(_sample(i, published_date=f"2020-01-0{i}"))
    store.rebuild_index()

    index = store.load_index()
    assert [a["id"] for a in index] == [1, 2, 3]  # sorted by id
    # Index entries are metadata only (no heavy body fields).
    assert "content_markdown" not in index[0]
    assert config.index_path().exists()


def test_load_index_raises_when_not_provisioned(data_dir) -> None:
    with pytest.raises(store.DataNotProvisionedError):
        store.load_index()


def test_load_index_returns_copies(data_dir) -> None:
    store.save_article(_sample(5))
    store.rebuild_index()
    a = store.load_index()
    a[0]["title"] = "MUTATED"
    b = store.load_index()
    assert b[0]["title"] != "MUTATED"  # cached/stored data not mutated
