"""Loading and validation of the LLM dataset files (spec §4, §5, §8, §15).

File format (both `confident.json` and `review.json`): a single JSON object
mapping lexical identity -> record. JSON is the working/generation format
for LLM output (spec §4); .u8 is only used for assembled dictionaries.

One record per lexical entry. Each record carries a `senses` list with one
sense per CEDICT gloss (spec §5: generation happens per gloss; §15: glosses
are tracked per generated definition). The sense list MUST cover exactly
the CC-CEDICT gloss set for the entry — same glosses, same count
(see `assert_gloss_coverage`, the accept/reject criterion). A record that
drops a gloss or invents one is rejected, never silently fixed (spec §14).

Every record must carry full provenance (spec §8):
  traditional, simplified, pinyin, senses[], confidence,
  cc_cedict_version, llm_model, prompt_version, generation_date

The record key must equal the record's own lexical identity, so the mapping
cannot silently disagree with itself (spec §14: fail rather than override).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..identity import compute_lexical_identity

REQUIRED_FIELDS = (
    "traditional",
    "simplified",
    "pinyin",
    "senses",
    "confidence",
    "cc_cedict_version",
    "llm_model",
    "prompt_version",
    "generation_date",
)

STRING_FIELDS = (
    "traditional",
    "simplified",
    "pinyin",
    "confidence",
    "cc_cedict_version",
    "llm_model",
    "prompt_version",
    "generation_date",
)

CONFIDENCE_VALUES = {"confident", "review"}


class LLMDataError(ValueError):
    """Raised when an LLM dataset file violates the expected structure."""


def record_glosses(record: dict[str, Any]) -> set[str]:
    """Return the set of source glosses covered by a record's senses."""
    return {sense["source_gloss"] for sense in record["senses"]}


def assert_gloss_coverage(record: dict[str, Any], expected_glosses: set[str]) -> None:
    """Accept/reject a record against the CC-CEDICT gloss set for its entry.

    The French output must define every English gloss of the entry — no
    fewer, no others. Raises LLMDataError naming the missing and/or extra
    glosses.
    """
    covered = record_glosses(record)
    expected = set(expected_glosses)
    missing = expected - covered
    extra = covered - expected
    if missing or extra:
        details = []
        if missing:
            details.append(f"missing French for gloss(es): {sorted(missing)}")
        if extra:
            details.append(f"gloss(es) not in CC-CEDICT: {sorted(extra)}")
        raise LLMDataError(
            f"{record.get('traditional', '?')}|{record.get('simplified', '?')}|"
            f"{record.get('pinyin', '?')}: gloss coverage mismatch — "
            + "; ".join(details)
        )


def validate_record(key: str, record: Any) -> str:
    """Validate one record; return its computed lexical identity.

    Raises LLMDataError describing the first problem found.
    """
    if not isinstance(record, dict):
        raise LLMDataError(f"{key}: record must be a JSON object")
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise LLMDataError(f"{key}: missing required field {field!r}")
    for field in STRING_FIELDS:
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise LLMDataError(f"{key}: field {field!r} must be a non-empty string")
    if record["confidence"] not in CONFIDENCE_VALUES:
        raise LLMDataError(
            f"{key}: confidence must be one of {sorted(CONFIDENCE_VALUES)}, "
            f"got {record['confidence']!r}"
        )
    senses = record["senses"]
    if not isinstance(senses, list) or not senses:
        raise LLMDataError(f"{key}: 'senses' must be a non-empty list")
    seen_glosses: set[str] = set()
    for i, sense in enumerate(senses):
        where = f"{key}: senses[{i}]"
        if not isinstance(sense, dict):
            raise LLMDataError(f"{where}: sense must be a JSON object")
        for field in ("source_gloss", "french_definition"):
            if field not in sense:
                raise LLMDataError(f"{where}: missing required field {field!r}")
            value = sense[field]
            if not isinstance(value, str) or not value.strip():
                raise LLMDataError(
                    f"{where}: field {field!r} must be a non-empty string"
                )
        if sense["source_gloss"] in seen_glosses:
            raise LLMDataError(
                f"{where}: duplicate source_gloss "
                f"{sense['source_gloss']!r} within one record"
            )
        seen_glosses.add(sense["source_gloss"])
    expected_key = compute_lexical_identity(
        record["traditional"], record["simplified"], record["pinyin"]
    )
    if key != expected_key:
        raise LLMDataError(
            f"{key}: record identity mismatch — key implies {key!r} but "
            f"record fields imply {expected_key!r}"
        )
    return expected_key


def load_llm_json(path: str | Path) -> dict[str, dict[str, str]]:
    """Load and fully validate an LLM dataset file.

    Returns the mapping identity -> record. Raises LLMDataError on any
    structural or relationship violation (spec §14).

    Note: gloss-coverage against CC-CEDICT (`assert_gloss_coverage`) is a
    separate step — the loader sees only the JSON file, not CC-CEDICT.
    Phase 9 wires the two together; the check itself lives here so both
    the generation pipeline and validation share one implementation.
    """
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise LLMDataError(f"{path}: invalid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise LLMDataError(f"{path}: top level must be a JSON object")

    validated: dict[str, dict[str, str]] = {}
    for key, record in data.items():
        if not isinstance(key, str) or not key.strip():
            raise LLMDataError(f"{path}: identity keys must be non-empty strings")
        validate_record(key, record)
        validated[key] = record
    return validated
