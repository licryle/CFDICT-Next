"""Release scope information (spec §12, §16).

Each release describes its source and resulting coverage: the CC-CEDICT
scope, the contributions of authoritative CFDICT / confident LLM / review
LLM data, and the two assembled dictionaries. Every figure derives from
the exact inputs of that release — versions are content hashes unless the
caller supplies explicit labels — so a release is traceable to the source
data that produced it.

The rendered markdown is the release-notes body consumed by the GitHub
workflow (Phase 10). No separate scope.json artifact is produced (§12).
Coverage counts reuse src/scope.py so scope info can never disagree with
the scope computation.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .scope import compute_scope_statistics


@dataclass(frozen=True)
class ReleaseSources:
    """Everything a release is traceable to."""

    cc_cedict_version: str
    cc_cedict_ids: set[str] = field(default_factory=set)
    cfdict_version: str = ""
    cfdict_ids: set[str] = field(default_factory=set)
    confident_version: str = ""
    confident_ids: set[str] = field(default_factory=set)
    review_version: str = ""
    review_ids: set[str] = field(default_factory=set)
    llm_models: tuple[str, ...] = ()
    prompt_versions: tuple[str, ...] = ()


def sha256_file(path: str | Path) -> str:
    """Short content hash identifying the exact bytes of a source file."""
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()[:12]


def collect_llm_provenance(
    records: dict[str, dict[str, Any]],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Distinct (llm_model, prompt_version) values across LLM records."""
    models = sorted({r.get("llm_model", "") for r in records.values()} - {""})
    prompts = sorted({r.get("prompt_version", "") for r in records.values()} - {""})
    return tuple(models), tuple(prompts)


def build_scope_info(
    sources: ReleaseSources, generated_at: str | None = None
) -> dict[str, Any]:
    """Build the scope information dict for one release."""
    if generated_at is None:
        generated_at = datetime.now(timezone.utc).isoformat()
    statistics = compute_scope_statistics(
        sources.cc_cedict_ids,
        sources.cfdict_ids,
        sources.confident_ids,
        sources.review_ids,
    )
    return {
        "generated_at": generated_at,
        "sources": {
            "cc_cedict": {
                "version": sources.cc_cedict_version,
                "entries": statistics["cc_cedict_total"],
            },
            "cfdict": {
                "version": sources.cfdict_version,
                "entries": statistics["cfdict_total"],
            },
            "llm_confident": {
                "version": sources.confident_version,
                "entries": statistics["llm_confident_total"],
            },
            "llm_review": {
                "version": sources.review_version,
                "entries": statistics["llm_review_total"],
            },
        },
        "provenance": {
            "llm_models": list(sources.llm_models),
            "prompt_versions": list(sources.prompt_versions),
        },
        "coverage": statistics,
    }


def render_scope_markdown(info: dict[str, Any]) -> str:
    """Render scope information as the release-notes body."""
    sources = info["sources"]
    coverage = info["coverage"]
    provenance = info["provenance"]
    lines = [
        "## Scope",
        "",
        f"Generated at {info['generated_at']}.",
        "",
        "| source | version | entries |",
        "| --- | --- | --- |",
        f"| CC-CEDICT (scope) | {sources['cc_cedict']['version']} "
        f"| {sources['cc_cedict']['entries']} |",
        f"| CFDICT (authoritative) | {sources['cfdict']['version']} "
        f"| {sources['cfdict']['entries']} |",
        f"| CFDICT-LLM confident | {sources['llm_confident']['version']} "
        f"| {sources['llm_confident']['entries']} |",
        f"| CFDICT-LLM review | {sources['llm_review']['version']} "
        f"| {sources['llm_review']['entries']} |",
        "",
        "## Coverage",
        "",
        f"- Missing scope (still to generate): {coverage['missing_scope_total']}",
        f"- Confident dictionary: {coverage['confident_dictionary_total']} entries",
        f"- Full dictionary: {coverage['full_dictionary_total']} entries",
        f"- CFDICT covers {coverage['cfdict_covers_cc_cedict']} CC-CEDICT entries",
        f"- Confident LLM covers {coverage['confident_covers_cc_cedict']} CC-CEDICT entries",
        f"- Review LLM covers {coverage['review_covers_cc_cedict']} CC-CEDICT entries",
        "",
        "## Provenance",
        "",
        f"- LLM models: {', '.join(provenance['llm_models']) or 'n/a'}",
        f"- Prompt versions: {', '.join(provenance['prompt_versions']) or 'n/a'}",
        "",
    ]
    return "\n".join(lines)
