# PyPI Release Checklist

Use this checklist before publishing a new version to PyPI.

## Pre-Release (1-2 days before)

### Code Quality
- [ ] Run full test suite: `pytest`
- [ ] Ensure test coverage = 100%: `pytest --cov=henchman --cov-report=term-missing --cov-fail-under=100`
- [ ] Run linting: `ruff check src/ tests/`
- [ ] Run formatting: `ruff format src/ tests/ --check`
- [ ] Run type checking: `mypy src/`
- [ ] Run security audit: `bandit -r src/`

### Documentation
- [ ] Update README.md with new features/changes
- [ ] Update CHANGELOG.md with release notes
- [ ] Update docs/ directory with any API changes
- [ ] Verify all links in documentation work
- [ ] Test documentation build: `mkdocs build`

### Version Management
- [ ] Update version in `pyproject.toml`
- [ ] Check dependency versions are up to date
- [ ] Test installation from local build: `hatch build && pip install dist/*.whl`
- [ ] Test basic functionality after fresh install

## Release Day

### Final Checks
- [ ] Create release branch: `git checkout -b release/vX.Y.Z`
- [ ] Run complete test suite one more time
- [ ] Verify CHANGELOG.md format and content
- [ ] Update any "Unreleased" sections in CHANGELOG.md
- [ ] Commit changes: `git commit -m "chore: release vX.Y.Z"`
- [ ] Tag release: `git tag -a vX.Y.Z -m "Release vX.Y.Z"`
- [ ] Push tag: `git push origin vX.Y.Z`

### Building
- [ ] Clean previous builds: `rm -rf dist/`
- [ ] Build package: `hatch build`
- [ ] Verify build artifacts:
  - [ ] `.whl` file exists
  - [ ] `.tar.gz` file exists
  - [ ] Files have correct permissions

### Testing Build
- [ ] Create test virtual environment: `python -m venv test_env`
- [ ] Install from test PyPI (if available)
- [ ] Test basic commands work
- [ ] Test with different Python versions (3.10, 3.11, 3.12)

### Publishing
- [ ] Upload to PyPI Test: `hatch publish -r testpypi`
- [ ] Verify on TestPyPI: https://test.pypi.org/project/henchman-ai/
- [ ] Install from TestPyPI: `pip install --index-url https://test.pypi.org/simple/ henchman-ai`
- [ ] Test installation from TestPyPI
- [ ] Upload to PyPI Production: `hatch publish`
- [ ] Verify on PyPI: https://pypi.org/project/henchman-ai/

## Post-Release

### GitHub
- [ ] Push release branch: `git push origin release/vX.Y.Z`
- [ ] Create GitHub Release from tag
- [ ] Copy CHANGELOG.md notes to GitHub Release
- [ ] Attach build artifacts to GitHub Release
- [ ] Merge release branch to main

### Communication
- [ ] Update any relevant issue trackers
- [ ] Announce on relevant channels (if applicable)
- [ ] Update any downstream dependencies

### Monitoring
- [ ] Monitor PyPI download stats
- [ ] Watch for issue reports
- [ ] Be available for support questions

## Rollback Plan

If issues are discovered after release:

1. **Minor issues**: Release patch version (X.Y.Z+1)
2. **Major issues**: 
   - Yank broken version from PyPI: `twine yank henchman-ai==X.Y.Z`
   - Release fixed version immediately
   - Communicate clearly about the issue and fix

## Versioning Strategy

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (X.0.0): Breaking API changes
- **MINOR** (0.X.0): New features, backward compatible
- **PATCH** (0.0.X): Bug fixes, backward compatible

## Common Issues to Check

- [ ] Import statements work correctly
- [ ] Entry points are registered properly
- [ ] All required files are included in package
- [ ] No large binary files accidentally included
- [ ] LICENSE file is included
- [ ] README.md renders correctly on PyPI
- [ ] All URLs in metadata are valid