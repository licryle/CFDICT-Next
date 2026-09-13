# Phase 5.7: Dictionary label abbreviations (prompt v2)

## Status: fix for LLM-test report on 行 xing2

Model output `(forme fermée) ...`, `(écriture littéraire) ...`,
`(prononcé en Taïwan ...)` — verbose calques of CEDICT parentheticals,
against CFDICT convention (`lit.`, `Tw`, no bound-form marker).

## Decisions (user, 2026-09-13)

- `(bound form)` → DROP (bare sense, no French marker)
- `(literary)` → `lit. ` prefix
- `(Taiwan pr. [X])` → `(Tw [X])` suffix

## Tasks

- [x] New versioned template `prompts/generate_fr_v2.txt` (v1 kept):
      label table + FORBIDDEN list
      (`forme fermée`, `écriture littéraire`, `prononcé en`, `à Taïwan` spelled out)
- [x] `PROMPT_VERSION` v1 → v2 in `src/generation/prompt.py`
- [x] 2 few-shot examples in `prompts/few_shot_examples.json`:
      促 cu4 (bound drop + lit.), 枕 zhen3 (bound drop + Tw)
- [x] Tests in `tests/test_generation.py`: version pin v2, updated
      counts (11 confident / 1 review / 22 senses), label-rule tests

## Validation checklist

- [x] `pytest tests/test_generation.py` green (25 passed)
- [x] Full suite green (125 passed)
- [ ] Human review + commit (do NOT commit from agent)
- [ ] Re-run LLM batch on 行 xing2 to confirm `lit.` / dropped labels
