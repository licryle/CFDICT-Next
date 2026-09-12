# Phase 4.5: LLM Generation Specification

## Step 4.5: Document LLM generation interface

### Tasks
- [ ] Create `docs/llm_input_spec.md` defining input format:
  - Chinese simplified
  - Chinese traditional
  - Pinyin
  - English CEDICT gloss
- [ ] Create `docs/llm_output_spec.md` defining output format:
  - Traditional form
  - Simplified form
  - Pinyin
  - Source CEDICT gloss
  - Generated French definition
  - Confidence classification (confident/review)
  - Source CC-CEDICT version
  - LLM model/version
  - Prompt version
  - Generation date
- [ ] Create `schemas/llm_output.json` with JSON schema for LLM output
- [ ] Write example LLM input/output in `examples/llm_example.json`
- [ ] Document classification criteria for confident vs review

### Validation checklist
- [ ] `docs/llm_input_spec.md` exists
- [ ] `docs/llm_output_spec.md` exists
- [ ] `schemas/llm_output.json` validates generated data
- [ ] Example input/output present
- [ ] Commit this step after human review