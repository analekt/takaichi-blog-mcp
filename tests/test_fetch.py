"""Tests for pure (non-network) helpers in fetch.py."""

from __future__ import annotations

from takaichi_blog_mcp import fetch


def test_timestamp_to_date() -> None:
    assert fetch._timestamp_to_date("20251021182115") == "2025-10-21"
    assert fetch._timestamp_to_date("20000830000000") == "2000-08-30"


def test_build_article_merges_record_and_parsed() -> None:
    record = {
        "id": 8,
        "original_url": "https://www.sanae.gr.jp/column_detail8.html",
        "latest_timestamp": "20251021182115",
        "wayback_url": "https://web.archive.org/web/20251021182115/https://www.sanae.gr.jp/column_detail8.html",
        "snapshot_url": "https://web.archive.org/web/20251021182115id_/https://www.sanae.gr.jp/column_detail8.html",
    }
    parsed = {
        "title": "ようやく臨時国会が召集されました。",
        "category": "5期目",
        "published_date": "2009-10-26",
        "date_source": "html",
        "content_markdown": "本文",
        "content_html": "<p>本文</p>",
    }
    article = fetch._build_article(record, parsed)

    assert article["id"] == 8
    assert article["title"] == parsed["title"]
    assert article["published_date"] == "2009-10-26"
    assert article["archived_date"] == "2025-10-21"  # derived from timestamp
    assert article["wayback_url"] == record["wayback_url"]
    assert article["content_markdown"] == "本文"
    # snapshot_url and content_html are not part of the stored schema
    assert "snapshot_url" not in article
    assert "content_html" not in article
