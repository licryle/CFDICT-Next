"""Assembling generation results into the LLM dataset files (Phase 5, spec §4, §8).

Results arrive per entry (identity plus full sense list); each becomes one
record stamped with full provenance, split by confidence into the
`confident.json` / `review.json` mappings. Writes are atomic (temp file +
rename) so an interrupted run never leaves a half-written dataset. Merging
into an existing file refuses to overwrite keys (spec §14: generation
targets the missing scope, so collisions mean a bug upstream).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .llm import GenerationResult
from .prompt import PROMPT_VERSION


@dataclass(frozen=True)
class Provenance:
    """Provenance stamped on every generated record (spec §8, §16)."""

    cc_cedict_version: str
    llm_model: str
    prompt_version: str = PROMPT_VERSION


def _identical_senses(senses: list[dict[str, str]]) -> bool:
    """True when every sense carries the same French text (sense blending)."""
    texts = {s["french_definition"].strip() for s in senses}
    return len(senses) > 1 and len(texts) == 1


def build_records(
    results: list[GenerationResult],
    provenance: Provenance,
    generation_date: str | None = None,
) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    """Group per-entry results into (confident, review) identity -> records.

    An entry whose senses all share one identical French text is forced to
    `review`: undifferentiated senses are the signature of a model that
    blended the glosses instead of defining each one.
    `generation_date` defaults to the current UTC time in ISO 8601; pass an
    explicit value for deterministic output (tests).
    """
    if generation_date is None:
        generation_date = datetime.now(timezone.utc).isoformat()
    confident: dict[str, dict[str, Any]] = {}
    review: dict[str, dict[str, Any]] = {}
    for result in results:
        senses = [
            {"source_gloss": s.gloss, "french_definition": s.french_definition}
            for s in result.senses
        ]
        confidence = result.confidence
        if _identical_senses(senses):
            confidence = "review"
        record = {
            "traditional": result.traditional,
            "simplified": result.simplified,
            "pinyin": result.pinyin,
            "senses": senses,
            "confidence": confidence,
            "cc_cedict_version": provenance.cc_cedict_version,
            "llm_model": provenance.llm_model,
            "prompt_version": provenance.prompt_version,
            "generation_date": generation_date,
        }
        (confident if confidence == "confident" else review)[result.key] = record
    return confident, review


def merge_records(
    existing: dict[str, dict[str, Any]], new: dict[str, dict[str, Any]]
) -> dict[str, dict[str, Any]]:
    """Merge new records into an existing dataset; refuse key overwrites."""
    collision = set(existing) & set(new)
    if collision:
        raise ValueError(
            f"refusing to overwrite {len(collision)} existing record(s), e.g. "
            f"{sorted(collision)[0]!r} — generate only the missing scope"
        )
    return {**existing, **new}


def write_llm_json(path: str | Path, data: dict[str, dict[str, Any]]) -> None:
    """Atomically write an LLM dataset file (sorted keys, UTF-8)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)
