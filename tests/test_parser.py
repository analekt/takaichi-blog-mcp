"""Parser tests driven by real Wayback HTML fixtures from the reference repo.

Each fixture pair (``{id}.html`` raw snapshot, ``{id}.json`` reference parse)
lets us validate the parser fully offline. We assert the structured metadata
fields exactly, and the body via substring checks (Markdown conversion differs
slightly between markdownify and the reference's Turndown).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from takaichi_blog_mcp.parser import ParseError, parse_article_html

FIXTURES = Path(__file__).parent / "fixtures"
FIXTURE_IDS = [8, 10, 40, 1428, 1488]


def _load_html(article_id: int) -> str:
    return (FIXTURES / f"{article_id}.html").read_text(encoding="utf-8")


def _load_expected(article_id: int) -> dict:
    return json.loads((FIXTURES / f"{article_id}.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("article_id", FIXTURE_IDS)
def test_parse_metadata_matches_reference(article_id: int) -> None:
    expected = _load_expected(article_id)
    result = parse_article_html(_load_html(article_id))

    assert result["title"] == expected["title"]
    assert result["category"] == expected["category"]
    assert result["published_date"] == expected["published_date"]
    assert result["date_source"] == "html"


@pytest.mark.parametrize("article_id", FIXTURE_IDS)
def test_parse_body_is_nonempty_and_plausible(article_id: int) -> None:
    expected = _load_expected(article_id)
    result = parse_article_html(_load_html(article_id))

    assert result["content_markdown"].strip()
    assert result["content_html"].strip()

    # The first ~10 chars of the reference body (minus leading full-width
    # space) should appear in our Markdown output.
    ref_snippet = expected["content_markdown"].lstrip("　 ").strip()[:10]
    assert ref_snippet in result["content_markdown"]


def test_category_whitespace_is_stripped() -> None:
    # id 1488's <title> category segment has trailing spaces in the raw HTML.
    result = parse_article_html(_load_html(1488))
    assert result["category"] == result["category"].strip()
    assert "  " not in result["category"].rstrip()


def test_missing_title_raises_parse_error() -> None:
    with pytest.raises(ParseError):
        parse_article_html("<html><body><p>no article markup</p></body></html>")


def test_date_source_is_none_when_date_missing() -> None:
    html = (
        '<div class="articleTit"><h2>タイトル</h2></div>'
        '<div class="system-free">本文</div>'
    )
    result = parse_article_html(html)
    assert result["published_date"] is None
    assert result["date_source"] is None

