"""Parse archived sanae.gr.jp column HTML into structured article data.

The markup is stable across the full 2000-2025 range of snapshots:

    <div class="articleTit ...">
        <h2>TITLE</h2>
        <p class="day">更新日：<time datetime="YYYY-MM-DD">...</time></p>
    </div>
    <div class="system-free ...">BODY HTML</div>

The category lives in the <title> tag as the second " | "-delimited segment:

    TITLE | CATEGORY | コラム | 高市早苗(たかいちさなえ)
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from bs4 import BeautifulSoup
from markdownify import markdownify as md


class ParseError(ValueError):
    """Raised when required article markup cannot be found in the HTML."""


_TITLE_SUFFIX_PARTS = 4  # TITLE | CATEGORY | コラム | 高市早苗(...)


def _extract_category(soup: BeautifulSoup) -> Optional[str]:
    """Pull the category from the pipe-delimited <title> tag."""
    if soup.title is None or not soup.title.string:
        return None
    parts = [p.strip() for p in soup.title.string.split("|")]
    # Expected layout: [title, category, "コラム", "高市早苗(...)"]
    if len(parts) >= 2 and parts[1]:
        return parts[1]
    return None


def parse_article_html(html: str) -> Dict[str, Any]:
    """Parse a raw archived column page into structured fields.

    Args:
        html: Raw HTML of a single ``column_detail{id}.html`` snapshot.

    Returns:
        Dict with keys ``title``, ``category``, ``published_date``,
        ``date_source``, ``content_markdown`` and ``content_html``.

    Raises:
        ParseError: If the title or body container is missing, which signals
            the page is not a parseable article (e.g. an error/redirect page).
    """
    soup = BeautifulSoup(html, "html.parser")

    title_block = soup.select_one("div.articleTit")
    h2 = title_block.select_one("h2") if title_block else None
    if h2 is None or not h2.get_text(strip=True):
        raise ParseError("Could not find article title (div.articleTit h2)")
    title = h2.get_text(strip=True)

    body = soup.select_one("div.system-free")
    if body is None:
        raise ParseError("Could not find article body (div.system-free)")

    published_date: Optional[str] = None
    time_tag = title_block.select_one("time[datetime]") if title_block else None
    if time_tag is not None:
        published_date = time_tag.get("datetime", "").strip() or None

    content_html = body.decode_contents().strip()
    content_markdown = md(content_html, heading_style="ATX").strip()

    return {
        "title": title,
        "category": _extract_category(soup),
        "published_date": published_date,
        # Only claim the date came from the HTML markup if we actually found it.
        "date_source": "html" if published_date else None,
        "content_markdown": content_markdown,
        "content_html": content_html,
    }
