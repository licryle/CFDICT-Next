#!/usr/bin/env python3
"""Cleanup CLI: maintain the LLM datasets as deltas over authoritative CFDICT.

Usage:
    python scripts/cleanup.py [--dry-run] [--cfdict PATH] [--confident PATH] [--review PATH]

Applies spec §9 precedence (CFDICT > confident.json > review.json),
rewriting the datasets atomically unless --dry-run is given.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cleanup import cleanup_files  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cfdict", default="data/cfdict.u8")
    parser.add_argument("--confident", default="data/confident.json")
    parser.add_argument("--review", default="data/review.json")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        report = cleanup_files(args.cfdict, args.confident, args.review, args.dry_run)
    except (ValueError, OSError) as exc:
        print(f"cleanup failed: {exc}", file=sys.stderr)
        return 1
    mode = "dry run — no files written" if args.dry_run else "datasets rewritten"
    print(f"cleanup done ({mode}):")
    print(
        f"  confident: {report.confident_before} -> {report.confident_after} "
        f"(removed {report.confident_removed_cfdict} now in CFDICT)"
    )
    print(
        f"  review: {report.review_before} -> {report.review_after} "
        f"(removed {report.review_removed_cfdict} now in CFDICT, "
        f"{report.review_removed_confident} now confident)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
