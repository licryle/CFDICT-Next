"""Validation of source data and assembled results (spec §14).

Every check fails loudly with a named reason instead of silently
overriding or discarding data. Checks:

1. cfdict.u8 parses with zero malformed lines.
2. CC-CEDICT parses with zero malformed lines.
3. confident.json / review.json load (structure, identity keys).
4. No CFDICT∩confident, CFDICT∩review, or confident∩review overlap.
5. Every LLM record covers exactly its CC-CEDICT gloss set
   (accept/reject via assert_gloss_coverage); no LLM record may reference
   an identity outside CC-CEDICT scope.
6. Scope information is consistent with the inputs it claims to describe.
7. Assembled outputs parse cleanly and contain exactly the expected
   identity sets (confident = CFDICT+confident, full = +review), with no
   duplicate lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .parser.json import LLMDataError, assert_gloss_coverage, load_llm_json
from .parser.u8 import parse_u8_file, parse_u8_line
from .scope_info import ReleaseSources, build_scope_info


@dataclass
class Check:
    """One named validation check and its outcome."""

    name: str
    passed: bool
    detail: str = ""


@dataclass
class ValidationReport:
    """Outcome of a validation run."""

    checks: list[Check] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(c.passed for c in self.checks)

    def failures(self) -> list[Check]:
        return [c for c in self.checks if not c.passed]


def _parse_or_fail(path: str | Path, label: str, report: ValidationReport):
    entries, errors = parse_u8_file(path)
    if errors:
        preview = "; ".join(f"line {n}: {msg}" for n, msg in errors[:5])
        report.checks.append(
            Check(f"{label} parses", False, f"{len(errors)} malformed line(s): {preview}")
        )
        return None
    report.checks.append(Check(f"{label} parses", True, f"{len(entries)} entries"))
    return entries


def _load_or_fail(path: str | Path, label: str, report: ValidationReport):
    try:
        data = load_llm_json(path)
    except (LLMDataError, OSError) as exc:
        report.checks.append(Check(f"{label} loads", False, str(exc)))
        return None
    report.checks.append(Check(f"{label} loads", True, f"{len(data)} records"))
    return data


def check_no_overlap(
    cfdict_ids: set[str],
    confident: dict[str, Any],
    review: dict[str, Any],
    report: ValidationReport,
) -> None:
    """Check 4: the three datasets are pairwise disjoint where required."""
    pairs = (
        ("CFDICT/confident", set(confident) & cfdict_ids),
        ("CFDICT/review", set(review) & cfdict_ids),
        ("confident/review", set(review) & set(confident)),
    )
    for name, overlap in pairs:
        if overlap:
            example = sorted(overlap)[0]
            report.checks.append(
                Check(
                    f"no {name} overlap",
                    False,
                    f"{len(overlap)} overlapping identit(ies), e.g. {example!r}",
                )
            )
        else:
            report.checks.append(Check(f"no {name} overlap", True))


def check_gloss_coverage(
    cc_glosses: dict[str, set[str]],
    confident: dict[str, Any],
    review: dict[str, Any],
    report: ValidationReport,
) -> None:
    """Check 5: every LLM record matches its CC-CEDICT gloss set exactly."""
    problems: list[str] = []
    for label, dataset in (("confident", confident), ("review", review)):
        for key, record in dataset.items():
            if key not in cc_glosses:
                problems.append(f"{label}:{key} is outside CC-CEDICT scope")
                continue
            try:
                assert_gloss_coverage(record, cc_glosses[key])
            except LLMDataError as exc:
                problems.append(f"{label}:{exc}")
    if problems:
        preview = "; ".join(problems[:5])
        report.checks.append(
            Check("LLM gloss coverage", False, f"{len(problems)} problem(s): {preview}")
        )
    else:
        total = len(confident) + len(review)
        report.checks.append(
            Check("LLM gloss coverage", True, f"{total} record(s) match CC-CEDICT")
        )


def check_scope_info(
    info: dict[str, Any], sources: ReleaseSources, report: ValidationReport
) -> None:
    """Check 6: scope information matches the inputs it describes."""
    expected = build_scope_info(sources, generated_at=info.get("generated_at"))
    if info == expected:
        report.checks.append(Check("scope info consistent", True))
    else:
        report.checks.append(
            Check("scope info consistent", False, "figures differ from recomputation")
        )


def check_outputs(
    confident_u8: str | Path,
    full_u8: str | Path,
    cfdict_ids: set[str],
    confident_ids: set[str],
    review_ids: set[str],
    report: ValidationReport,
) -> None:
    """Check 7: assembled outputs contain exactly the expected identities."""
    for label, path, expected in (
        ("confident output", confident_u8, cfdict_ids | confident_ids),
        ("full output", full_u8, cfdict_ids | confident_ids | review_ids),
    ):
        ids: list[str] = []
        try:
            with open(path, encoding="utf-8") as f:
                raw_lines = list(f)
        except OSError as exc:
            report.checks.append(Check(f"{label} parses", False, f"{path}: {exc}"))
            continue
        bad: list[str] = []
        for lineno, raw in enumerate(raw_lines, start=1):
            try:
                entry = parse_u8_line(raw)
            except ValueError as exc:
                bad.append(f"line {lineno}: {exc}")
                continue
            if entry is None:
                continue
            ids.append(entry.lexical_id())
        if bad:
            report.checks.append(
                Check(
                    f"{label} parses",
                    False,
                    f"{len(bad)} malformed line(s): " + "; ".join(bad[:3]),
                )
            )
            continue
        report.checks.append(Check(f"{label} parses", True))
        if len(set(ids)) != len(ids):
            report.checks.append(
                Check(
                    f"{label} has no duplicates",
                    False,
                    f"{len(ids) - len(set(ids))} duplicate line(s)",
                )
            )
            continue
        report.checks.append(Check(f"{label} has no duplicates", True))
        missing = expected - set(ids)
        extra = set(ids) - expected
        if missing or extra:
            detail = []
            if missing:
                detail.append(f"missing {len(missing)}, e.g. {sorted(missing)[0]!r}")
            if extra:
                detail.append(f"unexpected {len(extra)}, e.g. {sorted(extra)[0]!r}")
            report.checks.append(
                Check(f"{label} content", False, "; ".join(detail))
            )
        else:
            report.checks.append(
                Check(f"{label} content", True, f"{len(ids)} entries as expected")
            )


def validate_inputs(
    cfdict_path: str | Path,
    cc_cedict_path: str | Path,
    confident_path: str | Path,
    review_path: str | Path,
) -> tuple[ValidationReport, dict[str, Any] | None]:
    """Validate all release inputs; return (report, loaded data or None)."""
    report = ValidationReport()
    cfdict_entries = _parse_or_fail(cfdict_path, "cfdict.u8", report)
    cc_entries = _parse_or_fail(cc_cedict_path, "CC-CEDICT", report)
    confident = _load_or_fail(confident_path, "confident.json", report)
    review = _load_or_fail(review_path, "review.json", report)
    if None in (cfdict_entries, cc_entries, confident, review):
        return report, None
    assert cfdict_entries is not None and cc_entries is not None
    assert confident is not None and review is not None
    cfdict_ids = {e.lexical_id() for e in cfdict_entries}
    cc_glosses: dict[str, set[str]] = {}
    for e in cc_entries:
        cc_glosses.setdefault(e.lexical_id(), set()).update(e.definitions)
    check_no_overlap(cfdict_ids, confident, review, report)
    check_gloss_coverage(cc_glosses, confident, review, report)
    return report, {
        "cfdict_ids": cfdict_ids,
        "cc_glosses": cc_glosses,
        "confident": confident,
        "review": review,
    }
