# Phase 4: Identity and Scope Computation

## Step 4.1: Implement lexical identity computation

### Tasks
- [ ] Create `src/identity.py` with function `compute_lexical_id(entry)`
- [ ] Implement identity as combination of traditional + simplified + Pinyin
- [ ] Handle cases where Pinyin may not be present
- [ ] Write unit tests covering:
  - Traditional/simplified character pairs
  - Pinyin with tones
  - Missing Pinyin
  - Multiple pronunciations

### Validation checklist
- [ ] `src/identity.py` exists and is importable
- [ ] Function returns consistent ID for same input
- [ ] Tests pass for all cases
- [ ] Commit this step after human review

## Step 4.2: Implement scope computation

### Tasks
- [ ] Create `src/scope.py` with function `compute_scope(cc_cedict_version, cfdict_version, llm_confident_version, llm_review_version)`
- [ ] Implement logic to compute missing scope: CC-CEDICT - CFDICT - CFDICT-LLM
- [ ] Return scope as set of entry IDs
- [ ] Write unit tests with sample data showing:
  - Entries only in CC-CEDICT
  - Entries in CFDICT (should be excluded)
  - Entries in CFDICT-LLM (should be included)
  - Mixed cases

### Validation checklist
- [ ] `src/scope.py` exists
- [ ] Function correctly computes missing scope
- [ ] Tests cover all cases
- [ ] Commit this step after human review