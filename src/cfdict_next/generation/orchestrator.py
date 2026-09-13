"""Generation orchestrator: missing scope → batches → endpoint → datasets.

Orchestrates the Phase 5 pipeline end to end over real sources:

1. Parse CFDICT + CC-CEDICT, load the LLM datasets (all fail-loud).
2. Compute the missing scope (spec §3, §5) and build one item per entry
   with its full CC-CEDICT gloss list.
3. Generate in batches; accumulate ALL results before writing anything,
   so a failed batch leaves the datasets untouched.
4. Stamp provenance, split by confidence, merge into the existing files
   (key collisions refused), rewrite atomically.

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
from .llm import GenerationResult, generate_batch, post_chat_completions
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
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Generate all items in batches; return (confident, review) records."""
    results: list[GenerationResult] = []
    for chunk in batched(items, config.batch_size):
        results.extend(generate_batch(list(chunk), config, post=post))
    return build_records(results, provenance, generation_date)


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
    new_confident, new_review = generate_all(
        limited, config, provenance, generation_date, post
    )
    merged_confident = merge_records(confident, new_confident)
    merged_review = merge_records(review, new_review)
    write_llm_json(confident_path, merged_confident)
    write_llm_json(review_path, merged_review)
    return GenerationReport(
        plan=plan,
        confident_new=len(new_confident),
        review_new=len(new_review),
        dry_run=False,
    )
