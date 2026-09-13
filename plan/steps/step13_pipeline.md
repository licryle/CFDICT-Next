# Step 13: Local one-command pipeline

## Status: post-plan addition (user request)

Step 5 specified the generation pipeline but the repo had one CLI per
stage and no single local command. This step adds the orchestrating
entry point; CI keeps its granular stages (better logs), both calling
the same library functions so the paths cannot diverge.

## Step 13.1: Pipeline runner

### Tasks
- [ ] Create `src/cfdict_next/cli/pipeline.py` with staged
      generate → cleanup → validate → assemble → validate → scope,
      fail-fast with stage names
- [ ] Create `scripts/pipeline.py` shim (consistent with Step 3)
- [ ] Safety: `--limit` default 20 (0 = unlimited), `--dry-run` plans
      without endpoint or writes, `--skip-generate` for downstream-only
      re-runs, `--scope-out` (default `scope.md`, gitignored)

### Validation checklist
- [ ] Unit tests cover full run, dry-run purity, fail-fast stage
      attribution, and `--skip-generate` — all with a fake endpoint
- [ ] Real-data dry run works: `scripts/pipeline.py --dry-run`
- [ ] Full suite green
- [ ] Commit this step after human review
