# Phase 10: GitHub Actions Workflow

## Step 10.1: Create GitHub Actions workflow

### Tasks
- [ ] Create `.github/workflows/assemble.yml`
- [ ] Define triggers on updates to:
  - `cfdict.u8`
  - `confident.json`
  - `review.json`
- [ ] Implement workflow steps:
  - Check out repository
  - Enter Nix development environment
  - Run Python assembly script (`python src/assembly.py`)
  - Run Python validation script (`python src/validation.py`)
  - If validation passes:
    - Generate scope info
    - Publish GitHub release
    - Upload .u8 files as release assets
- [ ] Document workflow in `docs/workflow.md`
- [ ] Test workflow end-to-end with sample data

### Validation checklist
- [ ] Workflow file exists
- [ ] Triggers defined for relevant files
- [ ] Assembly and validation steps present
- [ ] Release publishing included
- [ ] Documentation written
- [ ] Commit this step after human review