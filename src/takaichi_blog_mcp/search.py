"""Pure, dependency-free search/filter logic over article dictionaries.

Japanese text is compared with plain substring matching (no tokenisation),
which works without any locale-specific dependencies. All functions are pure:
they read the given lists and return new lists, never mutating inputs.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

EXCERPT_CONTEXT = 60  # characters of context on each side of a match


def _by_date_desc(article: Dict[str, Any]):
    # Sort newest first; missing dates sort last.
    return (article.get("published_date") or "", article.get("id", 0))


def filter_articles(
    articles: List[Dict[str, Any]],
    category: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    """Filter metadata records by category/date range, newest first.

    Dates are ISO ``YYYY-MM-DD`` strings, compared lexicographically (which is
    correct for that format). ``limit``/``offset`` paginate the result.
    """
    result = list(articles)

    if category is not None:
        result = [a for a in result if a.get("category") == category]
    if date_from is not None:
        result = [a for a in result if (a.get("published_date") or "") >= date_from]
    if date_to is not None:
        result = [a for a in result if (a.get("published_date") or "") <= date_to]

    result.sort(key=_by_date_desc, reverse=True)

    if offset:
        result = result[offset:]
    if limit is not None:
        result = result[:limit]
    return [dict(a) for a in result]


def search_titles(
    articles: List[Dict[str, Any]],
    query: str,
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    """Return metadata records whose title contains ``query`` (substring)."""
    matches = [a for a in articles if query in (a.get("title") or "")]
    matches.sort(key=_by_date_desc, reverse=True)
    if limit is not None:
        matches = matches[:limit]
    return [dict(a) for a in matches]


def _make_excerpt(text: str, query: str) -> str:
    """Return a snippet of ``text`` centred on the first match of ``query``."""
    idx = text.find(query)
    if idx == -1:
        return text[: EXCERPT_CONTEXT * 2].strip()
    start = max(0, idx - EXCERPT_CONTEXT)
    end = min(len(text), idx + len(query) + EXCERPT_CONTEXT)
    snippet = text[start:end].strip().replace("\n", " ")
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{snippet}{suffix}"


def full_text_search(
    articles: List[Dict[str, Any]],
    query: str,
    limit: Optional[int] = 20,
) -> List[Dict[str, Any]]:
    """Substring-search title + body, returning matches with excerpts.

    Each article must include ``content_markdown``. Results are newest first
    and each carries an ``excerpt`` field showing context around the match.
    """
    hits: List[Dict[str, Any]] = []
    for article in articles:
        title = article.get("title") or ""
        body = article.get("content_markdown") or ""
        if query in title or query in body:
            source = body if query in body else title
            hit = {k: v for k, v in article.items() if k != "content_markdown"}
            hit["excerpt"] = _make_excerpt(source, query)
            hits.append(hit)

    hits.sort(key=_by_date_desc, reverse=True)
    if limit is not None:
        hits = hits[:limit]
    return hits
