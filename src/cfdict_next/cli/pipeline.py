"""Local end-to-end pipeline: generate → cleanup → validate → assemble.

Single entry point for a full local run over real sources. Each stage
uses the same library functions as the individual scripts (and therefore
the same code paths CI exercises step by step), failing fast with the
stage name on any violation.

Safety: --limit caps entries per run (default 0 = unlimited, unlike
scripts/generate.py whose default 20 stays capped); --dry-run plans
without endpoint calls or writes; --skip-generate re-runs only the
downstream stages over the current datasets.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from ..assembly import assemble_files
from ..cleanup import CleanupReport, cleanup_files
from ..generation.config import LLMConfig
from ..generation.llm import GenerationError
from ..generation.orchestrator import generate_files
from ..generation.llm import post_chat_completions
from ..scope_info import (
    ReleaseSources,
    build_scope_info,
    collect_llm_provenance,
    render_scope_markdown,
    sha256_file,
)
from ..validation import ValidationReport, check_outputs, validate_inputs


class PipelineError(Exception):
    """A pipeline stage failed; `stage` names which one."""

    def __init__(self, stage: str, message: str):
        super().__init__(f"[{stage}] {message}")
        self.stage = stage


@dataclass
class PipelineReport:
    """Outcome of a pipeline run."""

    dry_run: bool
    missing_scoped: int
    generated: int
    confident_new: int
    review_new: int
    cleanup: CleanupReport | None
    confident_n: int
    full_n: int
    scope_markdown: str


def _failures(report: ValidationReport) -> str:
    return "; ".join(
        f"{c.name}: {c.detail}" for c in report.failures()
    )


def run_pipeline(
    *,
    cfdict_path: str | Path,
    cc_cedict_path: str | Path,
    confident_path: str | Path,
    review_path: str | Path,
    out_confident_path: str | Path,
    out_full_path: str | Path,
    config: LLMConfig,
    cc_version: str | None = None,
    limit: int = 0,
    dry_run: bool = False,
    skip_generate: bool = False,
    scope_out: str | Path | None = None,
    post: Callable[..., Any] = post_chat_completions,
    generation_date: str | None = None,
) -> PipelineReport:
    """Run the full local pipeline; raise PipelineError on any failure."""
    cfdict_path, cc_cedict_path = Path(cfdict_path), Path(cc_cedict_path)
    confident_path, review_path = Path(confident_path), Path(review_path)

    try:
        cc_version = cc_version or sha256_file(cc_cedict_path)
    except OSError as exc:
        raise PipelineError("setup", f"cannot hash CC-CEDICT: {exc}") from exc

    if not dry_run and not skip_generate:
        try:
            gen_report = generate_files(
                cfdict_path,
                cc_cedict_path,
                confident_path,
                review_path,
                config,
                cc_version,
                limit=limit,
                dry_run=False,
                generation_date=generation_date,
                post=post,
            )
        except (ValueError, OSError, GenerationError) as exc:
            raise PipelineError("generate", str(exc)) from exc
    elif dry_run and not skip_generate:
        try:
            gen_report = generate_files(
                cfdict_path,
                cc_cedict_path,
                confident_path,
                review_path,
                config,
                cc_version,
                limit=limit,
                dry_run=True,
                post=post,
            )
        except (ValueError, OSError, GenerationError) as exc:
            raise PipelineError("generate", str(exc)) from exc
    else:
        gen_report = None

    if dry_run:
        # Read-only assessment of the current datasets; nothing downstream.
        report, _ = validate_inputs(
            cfdict_path, cc_cedict_path, confident_path, review_path
        )
        return PipelineReport(
            dry_run=True,
            missing_scoped=gen_report.plan.scoped if gen_report else 0,
            generated=0,
            confident_new=0,
            review_new=0,
            cleanup=None,
            confident_n=0,
            full_n=0,
            scope_markdown="",
        )

    try:
        cleanup_report = cleanup_files(cfdict_path, confident_path, review_path)
    except (ValueError, OSError) as exc:
        raise PipelineError("cleanup", str(exc)) from exc

    report, data = validate_inputs(
        cfdict_path, cc_cedict_path, confident_path, review_path
    )
    if data is None or not report.passed:
        raise PipelineError("validate-inputs", _failures(report))

    try:
        confident_n, full_n = assemble_files(
            cfdict_path,
            confident_path,
            review_path,
            out_confident_path,
            out_full_path,
        )
    except (ValueError, OSError) as exc:
        raise PipelineError("assemble", str(exc)) from exc

    out_report = ValidationReport()
    check_outputs(
        out_confident_path,
        out_full_path,
        data["cfdict_ids"],
        set(data["confident"]),
        set(data["review"]),
        out_report,
    )
    if not out_report.passed:
        raise PipelineError("validate-outputs", _failures(out_report))

    models, prompts = collect_llm_provenance({**data["confident"], **data["review"]})
    try:
        cfdict_version = sha256_file(cfdict_path)
        confident_version = sha256_file(confident_path)
        review_version = sha256_file(review_path)
    except OSError as exc:
        raise PipelineError("scope", f"cannot hash sources: {exc}") from exc
    sources = ReleaseSources(
        cc_cedict_version=cc_version,
        cc_cedict_ids=set(data["cc_glosses"]),
        cfdict_version=cfdict_version,
        cfdict_ids=data["cfdict_ids"],
        confident_version=confident_version,
        confident_ids=set(data["confident"]),
        review_version=review_version,
        review_ids=set(data["review"]),
        llm_models=models,
        prompt_versions=prompts,
    )
    markdown = render_scope_markdown(build_scope_info(sources))
    if scope_out is not None:
        try:
            Path(scope_out).write_text(markdown, encoding="utf-8")
        except OSError as exc:
            raise PipelineError("scope", f"cannot write scope file: {exc}") from exc

    return PipelineReport(
        dry_run=False,
        missing_scoped=gen_report.plan.scoped if gen_report else 0,
        generated=gen_report.plan.limited_to if gen_report else 0,
        confident_new=gen_report.confident_new if gen_report else 0,
        review_new=gen_report.review_new if gen_report else 0,
        cleanup=cleanup_report,
        confident_n=confident_n,
        full_n=full_n,
        scope_markdown=markdown,
    )


def main(argv: list[str] | None = None) -> int:
    """CLI entry point: full local pipeline in one command."""
    import argparse
    import dataclasses

    from ..generation.config import load_config

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", default=".env")
    parser.add_argument("--cfdict", default="data/cfdict.u8")
    parser.add_argument(
        "--cc-cedict", default="data/cc-cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz"
    )
    parser.add_argument("--confident", default="data/confident.json")
    parser.add_argument("--review", default="data/review.json")
    parser.add_argument("--out-confident", default="output/cfdict-next-confident.u8")
    parser.add_argument("--out-full", default="output/cfdict-next-full.u8")
    parser.add_argument("--cc-version", default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-generate", action="store_true")
    parser.add_argument("--scope-out", default="scope.md")
    args = parser.parse_args(argv)

    if args.limit < 0:
        print("pipeline failed: --limit must be >= 0 (0 = unlimited)")
        return 1
    try:
        config = load_config(args.env)
    except (ValueError, OSError) as exc:
        print(f"pipeline failed: {exc}")
        return 1
    if args.batch_size is not None:
        if args.batch_size <= 0:
            print("pipeline failed: --batch-size must be positive")
            return 1
        config = dataclasses.replace(config, batch_size=args.batch_size)
    try:
        report = run_pipeline(
            cfdict_path=args.cfdict,
            cc_cedict_path=args.cc_cedict,
            confident_path=args.confident,
            review_path=args.review,
            out_confident_path=args.out_confident,
            out_full_path=args.out_full,
            config=config,
            cc_version=args.cc_version,
            limit=args.limit,
            dry_run=args.dry_run,
            skip_generate=args.skip_generate,
            scope_out=None if args.dry_run else args.scope_out,
        )
    except PipelineError as exc:
        print(f"pipeline failed: {exc}")
        return 1
    if report.dry_run:
        print(
            "dry run — nothing called or written: "
            f"{report.missing_scoped} entries in missing scope"
        )
    else:
        dropped = 0
        if report.cleanup is not None:
            dropped = (
                report.cleanup.confident_removed_cfdict
                + report.cleanup.review_removed_cfdict
                + report.cleanup.review_removed_confident
            )
        print(
            f"pipeline done: generated {report.generated}/{report.missing_scoped} "
            f"({report.confident_new} confident, {report.review_new} review), "
            f"cleanup dropped {dropped}, "
            f"dictionaries {report.confident_n}/{report.full_n} entries"
        )
        if report.generated < report.missing_scoped:
            print(
                "scope truncated by --limit; re-run resumes the rest "
                "(already-written entries leave the missing scope)"
            )
    return 0
