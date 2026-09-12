# Phase 7: Assembly Script

## Step 7.1: Implement assembly logic

### Tasks
- [ ] Create `src/assembly.py` with function `assemble_dictionaries()`
- [ ] Implement precedence rules: CFDICT > confident.json > review.json
- [ ] Read authoritative CFDICT data from cfdict.u8
- [ ] Read LLM data from confident.json and review.json
- [ ] Apply precedence rules to merge entries
- [ ] Write unit tests for precedence logic

### Validation checklist
- [ ] `src/assembly.py` exists
- [ ] Precedence rules implemented correctly
- [ ] Unit tests pass
- [ ] Commit this step after human review

## Step 7.2: Produce confident and full .u8 dictionaries

### Tasks
- [ ] Extend `src/assembly.py` to write two output dictionaries:
  - Confident dictionary: CFDICT + confident.json
  - Full dictionary: CFDICT + confident.json + review.json
- [ ] Ensure output format is valid .u8
- [ ] Write integration tests for both outputs
- [ ] Document output file locations

### Validation checklist
- [ ] Confident .u8 dictionary produced
- [ ] Full .u8 dictionary produced
- [ ] Both outputs are valid .u8
- [ ] Integration tests pass
- [ ] Commit this step after human review