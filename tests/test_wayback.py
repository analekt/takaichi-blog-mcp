"""Tests for the pure CDX-row selection logic in wayback.py."""

from __future__ import annotations

from takaichi_blog_mcp import wayback


def test_select_latest_per_article_picks_max_timestamp() -> None:
    rows = [
        ["original", "timestamp"],  # header row
        ["https://www.sanae.gr.jp/column_detail8.html", "20220821015429"],
        ["https://www.sanae.gr.jp/column_detail8.html", "20251021182115"],
        ["https://www.sanae.gr.jp/column_detail10.html", "20230101000000"],
    ]
    result = wayback.select_latest_per_article(rows)
    by_id = {a["id"]: a for a in result}
    assert by_id[8]["latest_timestamp"] == "20251021182115"
    assert by_id[10]["latest_timestamp"] == "20230101000000"


def test_select_ignores_query_param_url_family() -> None:
    rows = [
        ["original", "timestamp"],
        ["https://www.sanae.gr.jp/column_detail.html?id=120", "20210101000000"],
        ["https://www.sanae.gr.jp/column_detail999.html", "20210101000000"],
    ]
    result = wayback.select_latest_per_article(rows)
    assert [a["id"] for a in result] == [999]


def test_select_builds_wayback_and_original_urls() -> None:
    rows = [
        ["original", "timestamp"],
        ["https://www.sanae.gr.jp/column_detail8.html", "20251021182115"],
    ]
    a = wayback.select_latest_per_article(rows)[0]
    assert a["id"] == 8
    assert a["original_url"] == "https://www.sanae.gr.jp/column_detail8.html"
    assert a["latest_timestamp"] == "20251021182115"
    assert "20251021182115" in a["wayback_url"]
    assert a["original_url"] in a["wayback_url"]


def test_select_result_sorted_by_id() -> None:
    rows = [
        ["original", "timestamp"],
        ["https://www.sanae.gr.jp/column_detail40.html", "20200101000000"],
        ["https://www.sanae.gr.jp/column_detail8.html", "20200101000000"],
        ["https://www.sanae.gr.jp/column_detail10.html", "20200101000000"],
    ]
    result = wayback.select_latest_per_article(rows)
    assert [a["id"] for a in result] == [8, 10, 40]


def test_select_handles_empty_rows() -> None:
    assert wayback.select_latest_per_article([]) == []
    assert wayback.select_latest_per_article([["original", "timestamp"]]) == []


def test_snapshot_url_uses_id_suffix() -> None:
    url = wayback.snapshot_url("20251021182115", "https://www.sanae.gr.jp/column_detail8.html")
    assert "id_/" in url
    assert url.endswith("https://www.sanae.gr.jp/column_detail8.html")
