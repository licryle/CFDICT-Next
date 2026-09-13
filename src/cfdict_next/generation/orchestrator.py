"""Generation orchestrator: missing scope → batches → endpoint → datasets.

Orchestrates the Phase 5 pipeline end to end over real sources:

1. Parse CFDICT + CC-CEDICT, load the LLM datasets (all fail-loud).
2. Compute the missing scope (spec §3, §5) and build one item per entry
   with its full CC-CEDICT gloss list.
3. Generate in batches; every successful batch is merged and written
   immediately, so a later failure never discards earlier progress.
4. A failed batch is retried entry-by-entry at the end of the pass, which
   isolates the poison entry: its batch-mates succeed, only the persistently
   failing keys are reported. Transport and validation errors are both
   retryable; keys still failing after the retry pass raise GenerationError
   (successes are already on disk, so a re-run resumes the rest).
5. Stamp provenance, split by confidence, merge into the existing files
   (key collisions refused), rewrite atomically per write.

Safety: `limit` caps entries per run (default 20) — a full-scope run
requires passing limit=0 explicitly. `dry_run` plans without touching
the endpoint or the files.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import batched
from pathlib import Path
from typing import Any, Callable

from ..cleanup import cfdict_identities
from ..parser.json import load_llm_json
from ..parser.u8 import DictionaryEntry, parse_u8_file
from .config import LLMConfig
from .llm import (
    GenerationError,
    GenerationResult,
    generate_batch,
    post_chat_completions,
)
from .output import Provenance, build_records, merge_records, write_llm_json
from .prompt import GenerationItem


@dataclass(frozen=True)
class GenerationPlan:
    """What a run would do (also returned by actual runs)."""

    scoped: int  # entries in missing scope
    limited_to: int  # entries after applying limit (0 = unlimited setting)
    batches: int  # batch calls the run makes/would make


@dataclass(frozen=True)
class GenerationReport:
    """Outcome of an orchestrator run."""

    plan: GenerationPlan
    confident_new: int
    review_new: int
    dry_run: bool


def compute_missing_items(
    cc_entries: list[DictionaryEntry],
    cfdict_ids: set[str],
    existing_ids: set[str],
) -> list[GenerationItem]:
    """Build one generation item per missing-scope entry, in CC-CEDICT order."""
    items: list[GenerationItem] = []
    seen: set[str] = set()
    for entry in cc_entries:
        key = entry.lexical_id()
        if key in cfdict_ids or key in existing_ids or key in seen:
            continue
        seen.add(key)
        items.append(
            GenerationItem(
                key=key,
                traditional=entry.traditional,
                simplified=entry.simplified,
                pinyin=entry.pinyin,
                glosses=tuple(entry.definitions),
            )
        )
    return items


def plan_generation(
    items: list[GenerationItem], batch_size: int, limit: int
) -> GenerationPlan:
    """Describe a run without executing it."""
    limited = items if limit <= 0 else items[:limit]
    batches = (len(limited) + batch_size - 1) // batch_size if limited else 0
    return GenerationPlan(scoped=len(items), limited_to=len(limited), batches=batches)


def generate_all(
    items: list[GenerationItem],
    config: LLMConfig,
    provenance: Provenance,
    generation_date: str | None = None,
    post: Callable[..., Any] = post_chat_completions,
    on_batch: Callable[
        [dict[str, dict[str, Any]], dict[str, dict[str, Any]]], None
    ]
    | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]], tuple[str, ...]]:
    """Generate all items in batches; return (confident, review, failed_keys).

    Every successful batch is converted to records and reported through
    `on_batch` immediately, so callers can persist progress as they go.
    A failed batch is deferred to a retry pass that runs each of its items
    alone (batch size 1): batch-mates of a poison entry still succeed, and
    only persistently failing keys land in `failed_keys`. Both transport
    and response-validation errors are retryable — `generate_batch` already
    retries each attempt up to `max_retries` before giving up on it.
    """
    confident: dict[str, dict[str, Any]] = {}
    review: dict[str, dict[str, Any]] = {}

    def _absorb(results: list[GenerationResult]) -> None:
        new_confident, new_review = build_records(
            results, provenance, generation_date
        )
        confident.update(new_confident)
        review.update(new_review)
        if on_batch is not None:
            on_batch(new_confident, new_review)

    deferred: list[list[GenerationItem]] = []
    for chunk in batched(items, config.batch_size):
        chunk = list(chunk)
        try:
            _absorb(generate_batch(chunk, config, post=post))
        except GenerationError:
            deferred.append(chunk)
    failed_keys: list[str] = []
    for chunk in deferred:
        for item in chunk:
            try:
                _absorb(generate_batch([item], config, post=post))
            except GenerationError:
                failed_keys.append(item.key)
    return confident, review, tuple(failed_keys)


def generate_files(
    cfdict_path: str | Path,
    cc_cedict_path: str | Path,
    confident_path: str | Path,
    review_path: str | Path,
    config: LLMConfig,
    cc_cedict_version: str,
    limit: int = 20,
    dry_run: bool = False,
    generation_date: str | None = None,
    post: Callable[..., Any] = post_chat_completions,
) -> GenerationReport:
    """Run generation against on-disk datasets; rewrite them unless dry_run."""
    cfdict_ids = cfdict_identities(cfdict_path)
    cc_entries, errors = parse_u8_file(cc_cedict_path)
    if errors:
        preview = "; ".join(f"line {n}: {msg}" for n, msg in errors[:5])
        raise ValueError(
            f"CC-CEDICT has {len(errors)} malformed line(s): {preview}"
        )
    confident = load_llm_json(confident_path, "confident")
    review = load_llm_json(review_path, "review")

    items = compute_missing_items(
        cc_entries, cfdict_ids, set(confident) | set(review)
    )
    plan = plan_generation(items, config.batch_size, limit)
    if dry_run:
        return GenerationReport(
            plan=plan, confident_new=0, review_new=0, dry_run=True
        )

    limited = items if limit <= 0 else items[:limit]
    provenance = Provenance(
        cc_cedict_version=cc_cedict_version, llm_model=config.model
    )

    def _persist(
        new_confident: dict[str, dict[str, Any]],
        new_review: dict[str, dict[str, Any]],
    ) -> None:
        """Merge one successful batch into the datasets and rewrite both files.

        Per-batch writes (each atomic via temp file + rename) mean a later
        failure keeps earlier progress on disk; the next run's missing-scope
        computation skips everything already written.
        """
        merged_confident = merge_records(confident, new_confident)
        merged_review = merge_records(review, new_review)
        write_llm_json(confident_path, merged_confident)
        write_llm_json(review_path, merged_review)
        confident.update(new_confident)
        review.update(new_review)

    new_confident, new_review, failed_keys = generate_all(
        limited, config, provenance, generation_date, post, on_batch=_persist
    )
    if failed_keys:
        raise GenerationError(
            f"{len(failed_keys)} entr{'y' if len(failed_keys) == 1 else 'ies'} "
            f"failed after retry, e.g. {failed_keys[0]!r} — "
            f"{len(new_confident) + len(new_review)} succeeded and were "
            "written; re-run resumes the rest"
        )
    return GenerationReport(
        plan=plan,
        confident_new=len(new_confident),
        review_new=len(new_review),
        dry_run=False,
    )
