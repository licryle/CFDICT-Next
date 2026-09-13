#!/usr/bin/env python3
"""Scope information CLI: describe one release's sources and coverage (spec §12).

Usage:
    python scripts/scope_info.py [--cfdict PATH] [--confident PATH] [--review PATH]
                                 [--cc-cedict PATH] [--cc-cedict-version LABEL]
                                 [--cfdict-version LABEL] [--confident-version LABEL]
                                 [--review-version LABEL] [--out PATH]

Version labels default to content hashes of the exact input bytes, so the
output is traceable to the sources even when no explicit version is given.
Prints the release-notes markdown to stdout (or --out).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.parser.json import load_llm_json  # noqa: E402
from src.parser.u8 import parse_u8_file  # noqa: E402
from src.scope_info import (  # noqa: E402
    ReleaseSources,
    build_scope_info,
    collect_llm_provenance,
    render_scope_markdown,
    sha256_file,
)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cfdict", default="data/cfdict.u8")
    parser.add_argument("--confident", default="data/confident.json")
    parser.add_argument("--review", default="data/review.json")
    parser.add_argument("--cc-cedict", default="data/cc-cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz")
    parser.add_argument("--cc-cedict-version", default=None)
    parser.add_argument("--cfdict-version", default=None)
    parser.add_argument("--confident-version", default=None)
    parser.add_argument("--review-version", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args(argv)

    try:
        cfdict_entries, errors = parse_u8_file(args.cfdict)
        if errors:
            preview = "; ".join(f"line {n}: {msg}" for n, msg in errors[:5])
            raise ValueError(f"cfdict.u8 has {len(errors)} malformed line(s): {preview}")
        cc_entries, errors = parse_u8_file(args.cc_cedict)
        if errors:
            preview = "; ".join(f"line {n}: {msg}" for n, msg in errors[:5])
            raise ValueError(f"CC-CEDICT has {len(errors)} malformed line(s): {preview}")
        confident = load_llm_json(args.confident, "confident")
        review = load_llm_json(args.review, "review")
    except (ValueError, OSError) as exc:
        print(f"scope info failed: {exc}", file=sys.stderr)
        return 1

    models, prompts = collect_llm_provenance({**confident, **review})
    sources = ReleaseSources(
        cc_cedict_version=args.cc_cedict_version or sha256_file(args.cc_cedict),
        cc_cedict_ids={e.lexical_id() for e in cc_entries},
        cfdict_version=args.cfdict_version or sha256_file(args.cfdict),
        cfdict_ids={e.lexical_id() for e in cfdict_entries},
        confident_version=args.confident_version or sha256_file(args.confident),
        confident_ids=set(confident),
        review_version=args.review_version or sha256_file(args.review),
        review_ids=set(review),
        llm_models=models,
        prompt_versions=prompts,
    )
    markdown = render_scope_markdown(build_scope_info(sources))
    if args.out:
        Path(args.out).write_text(markdown, encoding="utf-8")
    else:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
