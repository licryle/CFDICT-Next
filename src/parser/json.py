"""Loading and validation of the LLM dataset files (specification §4, §8).

File format (both `confident.json` and `review.json`): a single JSON object
mapping lexical identity -> record. JSON is the working/generation format for
LLM output (spec §4); .u8 is only used for assembled dictionary outputs.

Every record must carry full provenance (spec §8):
  traditional, simplified, pinyin, source_gloss, french_definition,
  confidence, cc_cedict_version, llm_model, prompt_version, generation_date

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
    "source_gloss",
    "french_definition",
    "confidence",
    "cc_cedict_version",
    "llm_model",
    "prompt_version",
    "generation_date",
)

STRING_FIELDS = set(REQUIRED_FIELDS)
CONFIDENCE_VALUES = {"confident", "review"}


class LLMDataError(ValueError):
    """Raised when an LLM dataset file violates the expected structure."""


def validate_record(key: str, record: Any) -> str:
    """Validate one record; return its computed lexical identity.

    Raises LLMDataError describing the first problem found.
    """
    if not isinstance(record, dict):
        raise LLMDataError(f"{key}: record must be a JSON object")
    for field in REQUIRED_FIELDS:
        if field not in record:
            raise LLMDataError(f"{key}: missing required field {field!r}")
        value = record[field]
        if not isinstance(value, str) or not value.strip():
            raise LLMDataError(f"{key}: field {field!r} must be a non-empty string")
    if record["confidence"] not in CONFIDENCE_VALUES:
        raise LLMDataError(
            f"{key}: confidence must be one of {sorted(CONFIDENCE_VALUES)}, "
            f"got {record['confidence']!r}"
        )
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
