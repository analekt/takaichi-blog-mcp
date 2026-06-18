"""FastMCP server exposing Sanae Takaichi's archived blog articles.

Transport: stdio (local subprocess launched by an MCP client such as Claude
Desktop). The server only reads the local data store; it never touches the
network. If the data has not been downloaded yet, every tool returns an
actionable message telling the user to run the provisioning command.

Tools:
    takaichi_list_articles      - list/filter metadata (category, date range)
    takaichi_list_categories    - list categories with article counts
    takaichi_get_article        - full Markdown + metadata for one article id
    takaichi_search_articles    - full-text search over titles + bodies
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel, ConfigDict, Field

from . import search, store

mcp = FastMCP("takaichi_blog_mcp")

_NOT_PROVISIONED_MSG = (
    "高市早苗ブログのデータがまだダウンロードされていません。"
    "先にプロビジョニングコマンドを実行してください:\n\n"
    "    takaichi-blog-fetch\n\n"
    "(または: python -m takaichi_blog_mcp.fetch)"
)


# --- helpers ---------------------------------------------------------------

def _load_index_or_error() -> Optional[List[Dict[str, Any]]]:
    """Return the index, or None if data is not provisioned."""
    try:
        return store.load_index()
    except store.DataNotProvisionedError:
        return None


def _load_all_full_articles() -> Optional[List[Dict[str, Any]]]:
    """Load every full article (with body) for full-text search."""
    if not store.is_provisioned():
        return None
    articles = []
    for article_id in store.iter_parsed_ids():
        article = store.load_article(article_id)
        if article is not None:
            articles.append(article)
    return articles


def _json(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2)


# --- input models ----------------------------------------------------------

class ListArticlesInput(BaseModel):
    """Filters for listing article metadata."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    category: Optional[str] = Field(
        default=None,
        description="Exact category name to filter by (see takaichi_list_categories)",
    )
    date_from: Optional[str] = Field(
        default=None,
        description="Earliest published date, inclusive (ISO 'YYYY-MM-DD', e.g. '2021-01-01')",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    date_to: Optional[str] = Field(
        default=None,
        description="Latest published date, inclusive (ISO 'YYYY-MM-DD')",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    limit: int = Field(default=20, description="Max results to return", ge=1, le=200)
    offset: int = Field(default=0, description="Results to skip for pagination", ge=0)


class GetArticleInput(BaseModel):
    """Identify a single article by numeric id."""
    model_config = ConfigDict(extra="forbid")

    id: int = Field(..., description="Article id (e.g. 8, 1428)", ge=1)


class SearchArticlesInput(BaseModel):
    """Full-text search query over titles and article bodies."""
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    query: str = Field(
        ...,
        description="Substring to search for in titles and bodies (Japanese text supported)",
        min_length=1,
        max_length=100,
    )
    limit: int = Field(default=20, description="Max results to return", ge=1, le=100)


# --- tools -----------------------------------------------------------------

@mcp.tool(
    name="takaichi_list_articles",
    annotations={
        "title": "List Takaichi blog articles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def takaichi_list_articles(params: ListArticlesInput) -> str:
    """List archived blog article metadata, newest first, with filtering.

    Filter by category and/or published-date range and paginate the results.
    Returns metadata only (no article body) — use takaichi_get_article to read
    a specific article's full text.

    Args:
        params (ListArticlesInput): category, date_from, date_to, limit, offset.

    Returns:
        str: JSON with schema:
        {
          "total": int,           # matches before pagination
          "count": int,           # items in this page
          "offset": int,
          "has_more": bool,
          "articles": [
            {"id": int, "title": str, "category": str,
             "published_date": str, "archived_date": str,
             "original_url": str, "wayback_url": str}
          ]
        }
        Or the provisioning message if data is not downloaded.
    """
    index = _load_index_or_error()
    if index is None:
        return _NOT_PROVISIONED_MSG

    filtered = search.filter_articles(
        index,
        category=params.category,
        date_from=params.date_from,
        date_to=params.date_to,
    )
    total = len(filtered)
    page = filtered[params.offset:params.offset + params.limit]
    return _json({
        "total": total,
        "count": len(page),
        "offset": params.offset,
        "has_more": params.offset + len(page) < total,
        "articles": page,
    })


@mcp.tool(
    name="takaichi_list_categories",
    annotations={
        "title": "List Takaichi blog categories",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def takaichi_list_categories() -> str:
    """List all blog categories with article counts and date ranges.

    Useful for discovering valid category values to pass to
    takaichi_list_articles, and for understanding the corpus structure
    (each category corresponds to a Diet term / period of her career).

    Returns:
        str: JSON with schema:
        {
          "total_articles": int,
          "categories": [
            {"category": str, "count": int,
             "earliest": str, "latest": str}  # ISO dates
          ]
        }
        Or the provisioning message if data is not downloaded.
    """
    index = _load_index_or_error()
    if index is None:
        return _NOT_PROVISIONED_MSG

    counts: Counter = Counter()
    earliest: Dict[str, str] = {}
    latest: Dict[str, str] = {}
    for a in index:
        cat = a.get("category") or "(uncategorized)"
        date = a.get("published_date") or ""
        counts[cat] += 1
        if date:
            if cat not in earliest or date < earliest[cat]:
                earliest[cat] = date
            if cat not in latest or date > latest[cat]:
                latest[cat] = date

    categories = [
        {
            "category": cat,
            "count": count,
            "earliest": earliest.get(cat),
            "latest": latest.get(cat),
        }
        for cat, count in counts.most_common()
    ]
    return _json({"total_articles": len(index), "categories": categories})


@mcp.tool(
    name="takaichi_get_article",
    annotations={
        "title": "Get a Takaichi blog article",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def takaichi_get_article(params: GetArticleInput) -> str:
    """Get the full Markdown body and metadata for one article by id.

    Always cite the source to the user using ``original_url`` (the original
    sanae.gr.jp page) and/or ``wayback_url`` (the Wayback Machine snapshot).

    Args:
        params (GetArticleInput): the numeric article id.

    Returns:
        str: JSON with schema:
        {
          "id": int, "title": str, "category": str,
          "published_date": str, "date_source": str, "archived_date": str,
          "original_url": str, "wayback_url": str,
          "content_markdown": str
        }
        Or an error message if the id is unknown / data not downloaded.
    """
    if not store.is_provisioned():
        return _NOT_PROVISIONED_MSG
    article = store.load_article(params.id)
    if article is None:
        return (f"Error: article id {params.id} not found. "
                f"Use takaichi_list_articles or takaichi_search_articles to "
                f"find valid ids.")
    return _json(article)


@mcp.tool(
    name="takaichi_search_articles",
    annotations={
        "title": "Search Takaichi blog articles",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def takaichi_search_articles(params: SearchArticlesInput) -> str:
    """Full-text search over article titles and bodies, newest first.

    Performs substring matching (Japanese supported) across every article's
    title and Markdown body. Each result includes a short excerpt with context
    around the match. Use takaichi_get_article with a returned id to read the
    full text.

    Args:
        params (SearchArticlesInput): query (substring) and limit.

    Returns:
        str: JSON with schema:
        {
          "query": str,
          "count": int,
          "results": [
            {"id": int, "title": str, "category": str,
             "published_date": str, "original_url": str,
             "wayback_url": str, "excerpt": str}
          ]
        }
        Or the provisioning message if data is not downloaded.
    """
    articles = _load_all_full_articles()
    if articles is None:
        return _NOT_PROVISIONED_MSG

    hits = search.full_text_search(articles, params.query, limit=params.limit)
    results = [
        {
            "id": h["id"],
            "title": h.get("title"),
            "category": h.get("category"),
            "published_date": h.get("published_date"),
            "original_url": h.get("original_url"),
            "wayback_url": h.get("wayback_url"),
            "excerpt": h.get("excerpt"),
        }
        for h in hits
    ]
    return _json({"query": params.query, "count": len(results), "results": results})


def main() -> None:
    """Entry point: run the MCP server over stdio."""
    mcp.run()


if __name__ == "__main__":
    main()
