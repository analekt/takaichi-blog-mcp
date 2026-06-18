"""Configuration constants and data-directory layout.

The data directory can be overridden with the ``TAKAICHI_BLOG_DATA_DIR``
environment variable (useful for tests and custom installs). All paths are
resolved lazily so that overriding the env var at runtime takes effect.
"""

from __future__ import annotations

import os
from pathlib import Path

# --- Wayback Machine endpoints ---------------------------------------------

CDX_API_URL = "https://web.archive.org/cdx/search/cdx"

# Prefix-match all column detail pages on the original site.
SOURCE_URL_PATTERN = "sanae.gr.jp/column_detail*"

# Template for fetching the raw (un-rewritten) archived HTML. The ``id_``
# suffix asks Wayback to return the original bytes without injecting its
# toolbar/rewrites.
SNAPSHOT_URL_TEMPLATE = "https://web.archive.org/web/{timestamp}id_/{url}"

# --- Politeness / retry -----------------------------------------------------

REQUEST_DELAY_SECONDS = 1.2
MAX_RETRIES = 3
RETRY_BACKOFF_SECONDS = (5, 10, 20)
REQUEST_TIMEOUT_SECONDS = 30.0
USER_AGENT = "takaichi-blog-mcp/0.1 (+https://github.com/analekt/takaichi-blog-dataset)"

# --- Local data layout ------------------------------------------------------

DATA_DIR_ENV_VAR = "TAKAICHI_BLOG_DATA_DIR"
DEFAULT_DATA_DIR = Path.home() / ".takaichi-blog-mcp"

INDEX_FILENAME = "articles.json"
CDX_FILENAME = "cdx-articles.json"
ARTICLES_SUBDIR = "articles"  # {id}.md
PARSED_SUBDIR = "parsed"      # {id}.json


def data_dir() -> Path:
    """Return the active data directory (env override or default)."""
    override = os.environ.get(DATA_DIR_ENV_VAR)
    return Path(override) if override else DEFAULT_DATA_DIR


def index_path() -> Path:
    return data_dir() / INDEX_FILENAME


def cdx_path() -> Path:
    return data_dir() / CDX_FILENAME


def parsed_path(article_id: int) -> Path:
    return data_dir() / PARSED_SUBDIR / f"{article_id}.json"


def markdown_path(article_id: int) -> Path:
    return data_dir() / ARTICLES_SUBDIR / f"{article_id}.md"
