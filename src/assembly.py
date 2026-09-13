"""Dictionary assembly (spec §10, §14).

Precedence:  CFDICT > confident.json > review.json

- The confident dictionary contains CFDICT + confident.json (§10.1).
- The full dictionary additionally contains review.json (§10.2).
- CFDICT always wins: `assemble` *raises* on any CFDICT∩LLM or
  confident∩review overlap instead of silently overriding (§14). Run the
  cleanup script first so the LLM datasets are proper deltas; Phase 9
  validation gates the workflow before assembly runs.
- Output order is deterministic: CFDICT file order, then LLM-only entries
  sorted by identity — so identical inputs always yield byte-identical
  outputs.
- Headword fields split on ASCII space/tab (a single CFDICT line uses
  tabs); U+3000 inside headwords is content and round-trips exactly.
- Definitions are strip-normalized on parse (a few dozen CFDICT lines
  carry incidental separator whitespace — "/ " gaps, "//" empties,
  even non-breaking spaces); the writer therefore emits canonical
  "/"-joined definitions. Content is preserved exactly — including
  U+3000 headwords — only incidental whitespace is normalized,
  deterministically.
- The writer restores U+3000 in headwords: the parser normalizes U+3000 to
  ASCII space on read, and no surviving ASCII space inside a headword can
  be original (fields split on ASCII space), so the reversal is exact.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .parser.json import load_llm_json
from .parser.u8 import DictionaryEntry, iter_u8_lines, parse_u8_file


def format_u8_entry(entry: DictionaryEntry) -> str:
    """Serialize one entry to a CEDICT line (LF ending, U+3000 restored)."""
    traditional = entry.traditional.replace(" ", "　")
    simplified = entry.simplified.replace(" ", "　")
    definitions = "/".join(entry.definitions)
    return f"{traditional} {simplified} [{entry.pinyin}] /{definitions}/\n"


def record_to_entry(key: str, record: dict[str, Any]) -> DictionaryEntry:
    """Convert one validated LLM record to a dictionary entry."""
    return DictionaryEntry(
        traditional=record["traditional"],
        simplified=record["simplified"],
        pinyin=record["pinyin"],
        definitions=tuple(s["french_definition"] for s in record["senses"]),
    )


def assemble(
    cfdict_entries: list[DictionaryEntry],
    confident: dict[str, dict[str, Any]],
    review: dict[str, dict[str, Any]],
) -> tuple[list[DictionaryEntry], list[DictionaryEntry]]:
    """Assemble (confident_entries, full_entries); raise on overlaps (§14)."""
    cfdict_ids = {e.lexical_id() for e in cfdict_entries}
    bad_confident = sorted(set(confident) & cfdict_ids)
    if bad_confident:
        raise ValueError(
            f"{len(bad_confident)} confident record(s) overlap CFDICT, e.g. "
            f"{bad_confident[0]!r} — run cleanup first"
        )
    bad_review = sorted((set(review) & cfdict_ids) | (set(review) & set(confident)))
    if bad_review:
        raise ValueError(
            f"{len(bad_review)} review record(s) overlap CFDICT/confident, e.g. "
            f"{bad_review[0]!r} — run cleanup first"
        )
    confident_extra = [
        record_to_entry(key, confident[key]) for key in sorted(confident)
    ]
    review_extra = [record_to_entry(key, review[key]) for key in sorted(review)]
    confident_entries = list(cfdict_entries) + confident_extra
    full_entries = list(cfdict_entries) + confident_extra + review_extra
    return confident_entries, full_entries


def write_u8_file(path: str | Path, entries: list[DictionaryEntry]) -> None:
    """Atomically write a .u8 dictionary file (UTF-8, LF endings)."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        for entry in entries:
            f.write(format_u8_entry(entry))
    tmp.replace(path)


def assemble_files(
    cfdict_path: str | Path,
    confident_path: str | Path,
    review_path: str | Path,
    out_confident_path: str | Path,
    out_full_path: str | Path,
) -> tuple[int, int]:
    """Full assembly from on-disk sources; return (confident_n, full_n)."""
    entries, errors = parse_u8_file(cfdict_path)
    if errors:
        preview = "; ".join(f"line {n}: {msg}" for n, msg in errors[:5])
        raise ValueError(f"cfdict.u8 has {len(errors)} malformed line(s): {preview}")
    confident = load_llm_json(confident_path)
    review = load_llm_json(review_path)
    confident_entries, full_entries = assemble(entries, confident, review)
    write_u8_file(out_confident_path, confident_entries)
    write_u8_file(out_full_path, full_entries)
    return len(confident_entries), len(full_entries)


def iter_output_lines(path: str | Path):
    """Yield entry lines of an assembled file (used by validation, Phase 9)."""
    yield from iter_u8_lines(path)
