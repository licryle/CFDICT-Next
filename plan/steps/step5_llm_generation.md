# Phase 5: LLM Generation Process

## Step 5.1: Implement offline LLM generation pipeline

### Tasks
- [ ] Create `src/generation/llm.py` with function `generate_entry(entry_id, chinese_simplified, chinese_traditional, pinyin, english_gloss)`
- [ ] Implement call to LLM API (to be configured via environment)
- [ ] Parse LLM response to extract French definition
- [ ] Apply classification logic (confident vs review)
- [ ] Generate provenance metadata (model, prompt, date)
- [ ] Write unit tests with mocked LLM response

### Validation checklist
- [ ] `src/generation/llm.py` exists
- [ ] Function takes input and returns JSON record
- [ ] Provenance metadata is complete
- [ ] Mock tests pass
- [ ] Commit this step after human review

## Step 5.2: Ensure provenance tracking in generated JSON files

### Tasks
- [ ] Create `src/generation/output.py` to write `confident.json` and `review.json`
- [ ] Ensure each entry has all provenance fields:
  - Traditional form
  - Simplified form
  - Pinyin
  - Source CEDICT gloss
  - Generated French definition
  - Confidence classification
  - Source CC-CEDICT version
  - LLM model/version
  - Prompt version
  - Generation date
- [ ] Write unit tests verifying all fields present
- [ ] Ensure JSON format matches schema from Phase 4.5

### Validation checklist
- [ ] `src/generation/output.py` exists
- [ ] Output files contain all provenance fields
- [ ] Format matches schema
- [ ] Tests pass
- [ ] Commit this step after human review