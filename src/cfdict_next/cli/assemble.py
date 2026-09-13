"""Assembly CLI: build the confident and full .u8 dictionaries (spec §10).

Usage:
    python scripts/assemble.py [--cfdict PATH] [--confident PATH] [--review PATH]
                               [--out-confident PATH] [--out-full PATH]

Inputs must already satisfy the precedence rules (run scripts/cleanup.py
and validation first): any CFDICT∩LLM or confident∩review overlap fails
the run instead of silently overriding (spec §14).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


from ..assembly import assemble_files


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cfdict", default="data/cfdict.u8")
    parser.add_argument("--confident", default="data/confident.json")
    parser.add_argument("--review", default="data/review.json")
    parser.add_argument("--out-confident", default="output/cfdict-next-confident.u8")
    parser.add_argument("--out-full", default="output/cfdict-next-full.u8")
    args = parser.parse_args(argv)

    try:
        confident_n, full_n = assemble_files(
            args.cfdict, args.confident, args.review,
            args.out_confident, args.out_full,
        )
    except (ValueError, OSError) as exc:
        print(f"assembly failed: {exc}", file=sys.stderr)
        return 1
    print(f"assembly done: confident {confident_n} entries -> {args.out_confident}, "
          f"full {full_n} entries -> {args.out_full}")
    return 0


