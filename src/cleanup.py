"""Cleanup: maintain the LLM datasets as deltas over authoritative CFDICT.

Precedence (spec §9):  CFDICT > confident.json > review.json

Rules:
- Drop from confident.json any entry now present in cfdict.u8.
- Drop from review.json any entry now present in cfdict.u8.
- Drop from review.json any entry present in confident.json.

Inputs are validated before use (spec §14): a malformed .u8 line or an
invalid LLM record fails the run instead of silently discarding data.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .parser.json import load_llm_json
from .parser.u8 import parse_u8_file


@dataclass(frozen=True)
class CleanupReport:
    """Counts describing what one cleanup run removed."""

    confident_before: int
    confident_removed_cfdict: int
    confident_after: int
    review_before: int
    review_removed_cfdict: int
    review_removed_confident: int
    review_after: int


def cfdict_identities(cfdict_path: str | Path) -> set[str]:
    """Parse cfdict.u8 and return its lexical identity set (fail on errors)."""
    entries, errors = parse_u8_file(cfdict_path)
    if errors:
        preview = "; ".join(f"line {n}: {msg}" for n, msg in errors[:5])
        raise ValueError(f"cfdict.u8 has {len(errors)} malformed line(s): {preview}")
    return {entry.lexical_id() for entry in entries}


def cleanup_datasets(
    cfdict_ids: set[str],
    confident: dict[str, dict[str, Any]],
    review: dict[str, dict[str, Any]],
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], CleanupReport]:
    """Apply the precedence rules; return (confident, review, report).

    Pure function over already-loaded data — the file I/O wrapper below
    handles reading, validating, and atomically rewriting the datasets.
    """
    confident_kept = {k: v for k, v in confident.items() if k not in cfdict_ids}
    review_kept = {
        k: v
        for k, v in review.items()
        if k not in cfdict_ids and k not in confident_kept
    }
    report = CleanupReport(
        confident_before=len(confident),
        confident_removed_cfdict=len(confident) - len(confident_kept),
        confident_after=len(confident_kept),
        review_before=len(review),
        review_removed_cfdict=len([k for k in review if k in cfdict_ids]),
        review_removed_confident=len(
            [k for k in review if k not in cfdict_ids and k in confident_kept]
        ),
        review_after=len(review_kept),
    )
    return confident_kept, review_kept, report


def cleanup_files(
    cfdict_path: str | Path,
    confident_path: str | Path,
    review_path: str | Path,
    dry_run: bool = False,
) -> CleanupReport:
    """Run cleanup against on-disk datasets; rewrite them unless dry_run."""
    from .generation.output import write_llm_json

    cfdict_ids = cfdict_identities(cfdict_path)
    confident = load_llm_json(confident_path)
    review = load_llm_json(review_path)
    confident_kept, review_kept, report = cleanup_datasets(
        cfdict_ids, confident, review
    )
    if not dry_run:
        write_llm_json(confident_path, confident_kept)
        write_llm_json(review_path, review_kept)
    return report
