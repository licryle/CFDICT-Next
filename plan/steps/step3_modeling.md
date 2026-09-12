# Phase 3: Data Modeling and Parsing

## Step 3.1: Define .u8 dictionary format and parser

### Tasks
- [ ] Research existing CEDICT .u8 format specification
- [ ] Create `src/parser/u8.py` with parser for .u8 files
- [ ] Implement dictionary entry data model (traditional, simplified, pinyin, definitions)
- [ ] Write unit tests for parser with sample .u8 file
- [ ] Handle encoding (UTF-8) and line endings

### Validation checklist
- [ ] `src/parser/u8.py` exists and is importable
- [ ] Parser correctly reads .u8 files
- [ ] Unit tests pass with sample data
- [ ] Commit this step after human review

## Step 3.2: Define JSON schemas for LLM data

### Tasks
- [ ] Design JSON schema for `confident.json` entries
- [ ] Design JSON schema for `review.json` entries
- [ ] Create schema files in `schemas/`
- [ ] Implement JSON loader in `src/parser/json.py`
- [ ] Write unit tests for JSON loader with sample data

### Validation checklist
- [ ] Schemas defined in `schemas/`
- [ ] JSON loader works for both files
- [ ] Unit tests pass
- [ ] Commit this step after human review

## Step 3.3: Implement entry identity scheme

### Tasks
- [ ] Define entry ID as combination of traditional + simplified + Pinyin
- [ ] Create `src/identity.py` with identity computation function
- [ ] Implement gloss tracking (individual CEDICT gloss per entry)
- [ ] Write unit tests for identity computation
- [ ] Document identity scheme in `docs/identity.md`

### Validation checklist
- [ ] `src/identity.py` exists
- [ ] Identity is deterministic for same input
- [ ] Tests handle multiple pronunciations per character
- [ ] Identity documented
- [ ] Commit this step after human review

## Step 3.4: Implement parsers for CC-CEDICT and CFDICT entries

### Tasks
- [ ] Create `src/parser/cc_cedict.py` for CC-CEDICT parsing
- [ ] Create `src/parser/cfdict.py` for CFDICT parsing
- [ ] Ensure parsers use common identity scheme
- [ ] Write unit tests for both parsers
- [ ] Handle format differences between CC-CEDICT and CFDICT

### Validation checklist
- [ ] Both parsers work and are tested
- [ ] Identity is consistent across both parsers
- [ ] Tests cover typical and edge cases
- [ ] Commit this step after human review