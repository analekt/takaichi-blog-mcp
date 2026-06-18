"""Provisioning CLI: download all archived articles into the local store.

Run once before starting the MCP server:

    takaichi-blog-fetch            # fetch any not-yet-downloaded articles
    takaichi-blog-fetch --force    # re-fetch everything
    takaichi-blog-fetch --dry-run  # show what would be fetched, fetch nothing

The full sweep is ~1,024 requests at ~1.2s each (~20 minutes) due to polite
rate limiting. This is intentionally a separate command, NOT part of server
startup, so MCP clients never block on it.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Dict, List

from . import config, store, wayback
from .parser import ParseError, parse_article_html


def _timestamp_to_date(timestamp: str) -> str:
    """Convert a 14-digit Wayback timestamp to an ISO date (YYYY-MM-DD)."""
    return f"{timestamp[0:4]}-{timestamp[4:6]}-{timestamp[6:8]}"


def _build_article(record: Dict[str, Any], parsed: Dict[str, Any]) -> Dict[str, Any]:
    """Merge a CDX record with parsed HTML into a full article dict."""
    return {
        "id": record["id"],
        "title": parsed["title"],
        "category": parsed["category"],
        "published_date": parsed["published_date"],
        "date_source": parsed["date_source"],
        "archived_date": _timestamp_to_date(record["latest_timestamp"]),
        "original_url": record["original_url"],
        "wayback_url": record["wayback_url"],
        "content_markdown": parsed["content_markdown"],
    }


def _save_cdx_index(records: List[Dict[str, Any]]) -> None:
    config.cdx_path().parent.mkdir(parents=True, exist_ok=True)
    config.cdx_path().write_text(
        json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8"
    )


async def _fetch_one(client, record: Dict[str, Any]) -> bool:
    """Fetch, parse and save a single article. Returns True on success."""
    try:
        html = await wayback.fetch_snapshot_html(client, record)
        parsed = parse_article_html(html)
    except ParseError as exc:
        print(f"  ! id {record['id']}: parse failed ({exc})", file=sys.stderr)
        return False
    except Exception as exc:  # network errors after retries exhausted
        print(f"  ! id {record['id']}: fetch failed ({type(exc).__name__}: {exc})",
              file=sys.stderr)
        return False
    store.save_article(_build_article(record, parsed))
    return True


async def run(force: bool, dry_run: bool) -> int:
    """Execute the provisioning workflow. Returns a process exit code."""
    print("Fetching CDX index from Wayback Machine ...")
    async with wayback.make_client() as client:
        records = await wayback.fetch_cdx_index(client)
        print(f"Found {len(records)} archived articles.")
        _save_cdx_index(records)

        if force:
            todo = records
        else:
            todo = [r for r in records if not config.parsed_path(r["id"]).exists()]

        skipped = len(records) - len(todo)
        if skipped:
            print(f"Skipping {skipped} already-downloaded articles "
                  f"(use --force to re-fetch).")

        if dry_run:
            print(f"[dry-run] Would fetch {len(todo)} articles. Nothing written.")
            for r in todo[:10]:
                print(f"  - id {r['id']}: {r['snapshot_url']}")
            if len(todo) > 10:
                print(f"  ... and {len(todo) - 10} more")
            return 0

        if not todo:
            print("Nothing to fetch. Rebuilding index ...")
            store.rebuild_index()
            print("Done.")
            return 0

        est_min = len(todo) * config.REQUEST_DELAY_SECONDS / 60
        print(f"Fetching {len(todo)} articles (~{est_min:.0f} min) ...")

        succeeded = 0
        for i, record in enumerate(todo, start=1):
            ok = await _fetch_one(client, record)
            succeeded += int(ok)
            if i % 25 == 0 or i == len(todo):
                print(f"  [{i}/{len(todo)}] fetched (ok={succeeded})")
            if i < len(todo):
                await asyncio.sleep(config.REQUEST_DELAY_SECONDS)

    print("Rebuilding aggregate index ...")
    store.rebuild_index()
    print(f"Done. {succeeded}/{len(todo)} articles saved to {config.data_dir()}")
    return 0 if succeeded else 1


def main(argv: List[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="takaichi-blog-fetch",
        description="Download Sanae Takaichi's archived blog articles from the "
                    "Wayback Machine into the local MCP data store.",
    )
    parser.add_argument("--force", action="store_true",
                        help="re-fetch all articles, even already-downloaded ones")
    parser.add_argument("--dry-run", action="store_true",
                        help="list what would be fetched without writing anything")
    args = parser.parse_args(argv)
    return asyncio.run(run(force=args.force, dry_run=args.dry_run))


if __name__ == "__main__":
    raise SystemExit(main())
