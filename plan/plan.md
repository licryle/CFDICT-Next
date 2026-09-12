# Plan for CFDICT-Next Implementation

## Overview
This plan breaks down the CFDICT-Next specification into small, human-reviewable steps. Each step is a self-contained task that can be committed and reviewed separately.

## Phase 1: Project Foundation
- [ ] Set up development environment (Nix, direnv, README)
- [ ] Create repository structure and initial commit

## Phase 2: Source Data Acquisition
- [ ] Acquire authoritative CFDICT corpus (cfdict.u8)
- [ ] Acquire CC-CEDICT data and version tracking
- [ ] Establish source data storage and versioning strategy

## Phase 3: Data Modeling and Parsing
- [ ] Define .u8 dictionary format and parser
- [ ] Define JSON schemas for confident.json and review.json
- [ ] Implement entry identity scheme (traditional + simplified + Pinyin)
- [ ] Implement parsers for CC-CEDICT and CFDICT entries

## Phase 4: Identity and Scope Computation
- [ ] Implement lexical identity computation
- [ ] Implement scope computation (CC-CEDICT - CFDICT - CFDICT-LLM)
- [ ] Create tests for identity and scope validation

## Phase 4.5: LLM Generation Specification
- [ ] Define LLM input format (Chinese sources + gloss)
- [ ] Define provenance schema for generated data
- [ ] Define classification criteria for confident vs review
- [ ] Document LLM output format requirements

## Phase 5: LLM Generation Process
- [ ] Implement offline LLM generation pipeline
- [ ] Ensure provenance tracking in generated JSON files
- [ ] Add version tagging for model, prompt, and generation date

## Phase 6: Cleanup Script
- [ ] Implement cleanup logic for confident.json (remove CFDICT entries)
- [ ] Implement cleanup logic for review.json (remove CFDICT and confident entries)
- [ ] Add verification tests for cleanup correctness

## Phase 7: Assembly Script
- [ ] Implement assembly logic with precedence CFDICT > confident > review
- [ ] Produce confident .u8 dictionary
- [ ] Produce full .u8 dictionary
- [ ] Integrate CC-CEDICT source consultation

## Phase 8: Scope Information Generation
- [ ] Implement scope information generation per release
- [ ] Include version tracking (CC-CEDICT, CFDICT, LLM data, model, prompt)
- [ ] Ensure scope info matches exact source versions used

## Phase 9: Validation Tooling
- [ ] Validate .u8 input files
- [ ] Validate JSON input files
- [ ] Validate entry identity consistency
- [ ] Validate no inappropriate overlap between datasets
- [ ] Validate scope information consistency
- [ ] Ensure assembly fails on validation errors

## Phase 10: GitHub Actions Workflow
- [ ] Create workflow that triggers on source data updates
- [ ] Implement assembly and release steps
- [ ] Ensure release outputs include .u8 files and scope info
- [ ] Test workflow end-to-end

## Phase 11: Documentation and Maintenance
- [ ] Write user documentation and contributor guide
- [ ] Define update procedures for CFDICT, CC-CEDICT, and LLM data
- [ ] Document reproducibility requirements
- [ ] Create maintenance checklist

## Phase 12: Final Review and Commitment
- [ ] Review all steps with human reviewer
- [ ] Sanction commits for each completed step
- [ ] Ensure all specifications are met