"""Tests for list/title/full-text search logic (pure functions over data)."""

from __future__ import annotations

import pytest

from takaichi_blog_mcp import search


@pytest.fixture
def articles():
    return [
        {"id": 1, "title": "臨時国会が召集", "category": "5期目", "published_date": "2009-10-26"},
        {"id": 2, "title": "普天間飛行場移設問題", "category": "5期目", "published_date": "2009-11-07"},
        {"id": 3, "title": "経済産業政策について", "category": "6期目", "published_date": "2013-03-01"},
        {"id": 4, "title": "総務省文書に関して", "category": "9期目", "published_date": "2023-03-24"},
    ]


@pytest.fixture
def full_articles(articles):
    bodies = {
        1: "本日ようやく臨時国会が召集されました。野党となった自民党の役割です。",
        2: "普天間飛行場移設問題の混迷を憂う。安全保障の観点から議論します。",
        3: "経済産業政策を担当することとなりました。成長戦略が重要です。",
        4: "総務省文書に関して参院予算委に提出した資料です。",
    }
    return [{**a, "content_markdown": bodies[a["id"]]} for a in articles]


def test_filter_by_category(articles) -> None:
    result = search.filter_articles(articles, category="5期目")
    assert {a["id"] for a in result} == {1, 2}


def test_filter_by_date_range(articles) -> None:
    result = search.filter_articles(articles, date_from="2010-01-01", date_to="2020-01-01")
    assert [a["id"] for a in result] == [3]


def test_filter_sorted_by_date_descending_by_default(articles) -> None:
    result = search.filter_articles(articles)
    assert [a["id"] for a in result] == [4, 3, 2, 1]


def test_filter_pagination(articles) -> None:
    page = search.filter_articles(articles, limit=2, offset=1)
    assert [a["id"] for a in page] == [3, 2]


def test_search_titles_substring(articles) -> None:
    result = search.search_titles(articles, "国会")
    assert [a["id"] for a in result] == [1]


def test_full_text_search_finds_body_matches(full_articles) -> None:
    hits = search.full_text_search(full_articles, "安全保障")
    assert len(hits) == 1
    assert hits[0]["id"] == 2
    assert "安全保障" in hits[0]["excerpt"]


def test_full_text_search_matches_title_too(full_articles) -> None:
    hits = search.full_text_search(full_articles, "経済産業")
    assert hits[0]["id"] == 3


def test_full_text_search_respects_limit(full_articles) -> None:
    hits = search.full_text_search(full_articles, "。", limit=2)
    assert len(hits) == 2


def test_full_text_search_no_match_returns_empty(full_articles) -> None:
    assert search.full_text_search(full_articles, "存在しない語句") == []
