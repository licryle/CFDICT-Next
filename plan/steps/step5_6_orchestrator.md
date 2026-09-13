# Phase 5.6: Generation orchestrator

## Status: gap-fill (not in the original plan)

The original plan specified the generation pipeline (Step 5.1) and the
dataset writer (Step 5.2) but no script wiring them together — manual
snippets filled the hole during testing. This step adds the missing
orchestration.

## Step 5.6.1: Orchestrator core and CLI

### Tasks
- [ ] Create `src/generation/orchestrator.py` with missing-scope item planning,
      batched generation over accumulated results, and atomic dataset merge
- [ ] Create `scripts/generate.py` CLI with `--env`, input paths,
      `--cc-version`, `--batch-size`, `--limit` (default 20, 0 = unlimited),
      `--dry-run`
- [ ] Safety: limit truncates per run (resume-friendly — written entries
      leave the missing scope); dry-run plans without endpoint or writes;
      failures write nothing (all batches complete before any merge/write)

### Validation checklist
- [ ] `src/generation/orchestrator.py` exists, imports cleanly
- [ ] `scripts/generate.py --help` works; `--dry-run` writes nothing
- [ ] Unit tests cover planning, batching, limit, dry-run, merge,
      provenance, and fail-loud batch errors — all with a fake endpoint
- [ ] Full suite green
- [ ] Commit this step after human review

## Step 5.6.2: Resilient generation (user request)

Atomic writes are replaced by incremental ones: every successful batch is
merged and written immediately, so a later failure keeps earlier progress.
A failed batch is retried entry-by-entry at the end of the pass (poison
isolation); transport and validation errors are both retryable. Keys still
failing after the retry pass raise `GenerationError` naming them — the
successes are already on disk, so a re-run resumes exactly the failures.

### Validation checklist
- [x] `generate_all` returns `(confident, review, failed_keys)` with an
      `on_batch` persistence hook; `generate_files` persists per batch
- [x] Unit tests cover poison isolation, resume, transient recovery, and
      per-batch callbacks — all with a fake endpoint
- [x] Full suite green
- [ ] Commit this step after human review
