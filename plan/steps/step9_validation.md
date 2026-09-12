# Phase 9: Validation Tooling

## Step 9.1: Implement validation script

### Tasks
- [ ] Create `src/validation.py` with function `validate_all()`
- [ ] Implement validation for valid .u8 input files
- [ ] Implement validation for valid JSON input files
- [ ] Implement validation for consistent dictionary entry identity
- [ ] Implement validation for no inappropriate overlap between CFDICT and LLM datasets
- [ ] Implement validation for no inappropriate overlap between confident.json and review.json
- [ ] Implement validation for consistent scope information
- [ ] Implement validation for consistent assembled output
- [ ] Write tests for each validation rule
- [ ] Ensure assembly fails when validation errors occur

### Validation checklist
- [ ] `src/validation.py` exists
- [ ] All validation rules implemented
- [ ] Tests pass for each rule
- [ ] Assembly fails on validation errors
- [ ] Commit this step after human review