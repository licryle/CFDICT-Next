# Phase 2: Source Data Acquisition

## Step 2.1: Acquire authoritative CFDICT corpus

### Tasks
- [ ] Create `data/` directory structure for source data
- [ ] Download authoritative `cfdict.u8` from CFDICT GitHub repository
- [ ] Store `cfdict.u8` in the project (or as a tracked submodule)
- [ ] Verify file integrity (line count, format)
- [ ] Document source URL and version

### Validation checklist
- [ ] `cfdict.u8` present in `data/`
- [ ] File format matches expected CEDICT format
- [ ] Source URL recorded in documentation
- [ ] Commit this step after human review

## Step 2.2: Acquire CC-CEDICT data

### Tasks
- [ ] Download CC-CEDICT data
- [ ] Store CC-CEDICT data in `data/` directory
- [ ] Record CC-CEDICT version and commit hash
- [ ] Document CC-CEDICT source and update procedure

### Validation checklist
- [ ] CC-CEDICT data present in `data/`
- [ ] Version recorded in documentation
- [ ] Update procedure documented
- [ ] Commit this step after human review

## Step 2.3: Establish source data storage and versioning

### Tasks
- [ ] Decide on storage strategy (git submodule vs. tracked files vs. download scripts)
- [ ] Document versioning policy for CFDICT, CC-CEDICT, and LLM data
- [ ] Create `data/README.md` describing data sources and versions

### Validation checklist
- [ ] Storage strategy documented
- [ ] Versioning policy documented
- [ ] `data/README.md` exists
- [ ] Commit this step after human review