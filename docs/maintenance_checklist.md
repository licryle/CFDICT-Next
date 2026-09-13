# Maintenance checklist

## Periodic

- [ ] CC-CEDICT freshness — is the snapshot in `data/` older than the
      release cadence demands? If yes, follow `update_procedures.md`.
- [ ] Review queue size — `python -c` on `data/review.json` record count;
      a growing queue means generation outpaces human review.
- [ ] Dependency health — `nix flake update` dry-run; `pip` audit of
      `jsonschema`/`pyyaml` for advisories.

## On demand

- [ ] CFDICT upstream fix → fork file → `cleanup` → review diff →
      `validate` → commit.
- [ ] New prompt version → template file + `PROMPT_VERSION` bump → trial
      generations → suite green → commit.
- [ ] New model → `.env` change (local only) → trial batch → judge
      French quality + confidence honesty before any bulk run.

## Per release (CI does it, human confirms)

- [ ] Actions run green (test → validate → assemble → validate → scope).
- [ ] Release notes figures sane (missing scope moves only as expected).
- [ ] Both `cfdict-next-*.u8` assets attached.

## Troubleshooting

| symptom | cause → fix |
|---|---|
| `validate` reports overlap | LLM datasets stale vs CFDICT → run `scripts/cleanup.py`, review diff, commit |
| `validate` reports gloss mismatch | CC-CEDICT drifted under existing records → regenerate affected entries or pin the older snapshot |
| `assemble` refuses overlap | same as overlap above — assembly never overrides; clean first |
| `generate` `GenerationError: missing id` | model dropped an entry — retry; persistent drops mean the batch is too large or the model too small |
| everything `review`, nothing `confident` | prompt/model verdict miscalibrated — check few-shot, try `--limit 3` trials |
| `nix develop` broken | `nix flake check`; fallback is venv + `pip install -e .` (sets `PYTHONPATH` equivalent) |
| CI red on `gh release` | check `contents: write` permission and tag collision (two pushes within one second) |
