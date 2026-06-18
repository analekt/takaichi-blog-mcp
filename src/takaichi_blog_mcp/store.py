"""Local persistence for fetched/parsed articles.

Layout under the data directory (see :mod:`takaichi_blog_mcp.config`):

    articles.json          aggregate metadata index (no body fields)
    parsed/{id}.json       full parsed article incl. content
    articles/{id}.md       YAML-frontmatter Markdown (human-friendly)
    raw/{id}.html          raw archived HTML (optional cache)

All reads return fresh copies so callers can never mutate stored state.
"""

from __future__ import annotations

import copy
import json
from typing import Any, Dict, List, Optional

from . import config

# Fields included in the lightweight aggregate index (everything except the
# large body fields).
_INDEX_FIELDS = (
    "id",
    "title",
    "category",
    "published_date",
    "date_source",
    "archived_date",
    "original_url",
    "wayback_url",
)

# Fields persisted per article. We store Markdown only (no raw/content HTML)
# per the chosen storage policy.
_ARTICLE_FIELDS = _INDEX_FIELDS + ("content_markdown",)


class DataNotProvisionedError(RuntimeError):
    """Raised when the local data store has not been populated yet."""

    def __init__(self) -> None:
        super().__init__(
            "Blog data has not been downloaded yet. Run the provisioning "
            "command first:\n\n    takaichi-blog-fetch\n\n"
            "(or: python -m takaichi_blog_mcp.fetch)"
        )


def _write_json(path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _frontmatter_markdown(article: Dict[str, Any]) -> str:
    """Render an article as YAML-frontmatter Markdown."""
    lines = ["---"]
    for key in _INDEX_FIELDS:
        value = article.get(key)
        if value is None:
            continue
        lines.append(f"{key}: {value}")
    lines.append("---")
    lines.append("")
    lines.append(article.get("content_markdown", ""))
    return "\n".join(lines) + "\n"


def is_provisioned() -> bool:
    """Return True if the aggregate index exists (data has been downloaded)."""
    return config.index_path().exists()


def save_article(article: Dict[str, Any]) -> None:
    """Persist a single article as Markdown + metadata JSON.

    Only Markdown content is stored; any ``content_html`` on the input is
    intentionally dropped (storage policy: Markdown only).
    """
    article_id = article["id"]
    record = {k: article.get(k) for k in _ARTICLE_FIELDS}
    _write_json(config.parsed_path(article_id), record)
    md_path = config.markdown_path(article_id)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.write_text(_frontmatter_markdown(record), encoding="utf-8")


def load_article(article_id: int) -> Optional[Dict[str, Any]]:
    """Load a single full article by id, or None if not present."""
    path = config.parsed_path(article_id)
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def iter_parsed_ids() -> List[int]:
    """Return sorted ids of all parsed articles on disk."""
    parsed_dir = config.data_dir() / config.PARSED_SUBDIR
    if not parsed_dir.exists():
        return []
    ids = []
    for path in parsed_dir.glob("*.json"):
        try:
            ids.append(int(path.stem))
        except ValueError:
            continue
    return sorted(ids)


def rebuild_index() -> List[Dict[str, Any]]:
    """Rebuild ``articles.json`` from the parsed/ directory and return it."""
    index: List[Dict[str, Any]] = []
    for article_id in iter_parsed_ids():
        article = load_article(article_id)
        if article is None:
            continue
        index.append({k: article.get(k) for k in _INDEX_FIELDS})
    _write_json(config.index_path(), index)
    return copy.deepcopy(index)


def load_index() -> List[Dict[str, Any]]:
    """Load the aggregate metadata index (fresh copy).

    Raises:
        DataNotProvisionedError: If the data store has not been populated.
    """
    if not is_provisioned():
        raise DataNotProvisionedError()
    data = json.loads(config.index_path().read_text(encoding="utf-8"))
    return copy.deepcopy(data)
