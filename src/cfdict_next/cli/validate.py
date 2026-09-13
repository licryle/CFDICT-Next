"""Validation CLI: gate releases on data relationships (spec §14).

Usage:
    python scripts/validate.py [--cfdict PATH] [--cc-cedict PATH]
                               [--confident PATH] [--review PATH]
                               [--out-confident PATH] [--out-full PATH]

Validates inputs always; validates assembled outputs when both --out-*
paths are given. Exits 1 with named reasons on any violation.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


from ..validation import check_outputs, validate_inputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cfdict", default="data/cfdict.u8")
    parser.add_argument(
        "--cc-cedict", default="data/cc-cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
    )
    parser.add_argument("--confident", default="data/confident.json")
    parser.add_argument("--review", default="data/review.json")
    parser.add_argument("--out-confident", default=None)
    parser.add_argument("--out-full", default=None)
    args = parser.parse_args(argv)

    report, data = validate_inputs(
        args.cfdict, args.cc_cedict, args.confident, args.review
    )
    if data is not None and args.out_confident and args.out_full:
        check_outputs(
            args.out_confident,
            args.out_full,
            data["cfdict_ids"],
            set(data["confident"]),
            set(data["review"]),
            report,
        )
    for check in report.checks:
        status = "ok  " if check.passed else "FAIL"
        detail = f" — {check.detail}" if check.detail else ""
        print(f"{status} {check.name}{detail}")
    if not report.passed:
        print(f"validation failed: {len(report.failures())} check(s)", file=sys.stderr)
        return 1
    print("validation passed")
    return 0


