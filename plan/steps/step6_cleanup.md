# Phase 6: Cleanup Script

## Step 6.1: Implement cleanup script

### Tasks
- [ ] Create `scripts/cleanup.py` with function `cleanup_datasets()`
- [ ] Implement logic to remove entries from confident.json:
  - If entry exists in cfdict.u8, remove from confident.json
- [ ] Implement logic to remove entries from review.json:
  - If entry exists in cfdict.u8, remove from review.json
  - If entry exists in confident.json, remove from review.json
- [ ] Write verification tests to confirm cleanup correctness
- [ ] Document usage and run instructions

### Validation checklist
- [ ] `scripts/cleanup.py` exists
- [ ] Cleanup logic matches specification
- [ ] Tests verify removal correctness
- [ ] Documentation present
- [ ] Commit this step after human review