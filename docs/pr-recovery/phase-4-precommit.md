# 🔧 Phase 4: Pre-commit Hook Preparation + Re-verification (30 min)

**Goal**: Ensure all code quality checks pass before final commit creation
**Status**: ⏳ Pending (starts after Phase 3 completion)
**Prerequisites**: ≤18 failing tests, all enhanced functionality preserved

## 🎯 Quality Gate Requirements

Before creating the final commit, we must ensure:
- ✅ All pre-commit hooks pass naturally (NO `--no-verify` usage)
- ✅ Code formatting and linting meet project standards
- ✅ Type checking passes without errors
- ✅ Security checks pass without violations
- ✅ All changes are staging-ready

## 📋 Pre-commit Preparation Steps

### Step 1: Code Formatting (10 min)
**Goal**: Apply consistent formatting to all modified files

```bash
# Format Python code
black app/ tests/ --line-length=100

# Sort and organize imports
isort app/ tests/ --profile black --line-length=100

# Verify formatting applied correctly
black app/ tests/ --check --line-length=100
isort app/ tests/ --check-only --profile black --line-length=100
```

**Expected Changes**:
- Consistent formatting across all enhanced files
- Proper import organization in new model classes
- Clean formatting in all test files with service pattern fixes

### Step 2: Linting and Auto-fixes (10 min)
**Goal**: Fix all auto-fixable linting issues

```bash
# Fix auto-fixable linting issues
ruff check app/ tests/ --fix

# Check remaining linting issues
ruff check app/ tests/

# Target: <25 violations (acceptable threshold)
```

**Focus Areas**:
- Enhanced response adapter methods
- New model class definitions
- Service pattern fixes in test files
- Async/await patterns in service mocking

### Step 3: Type Checking and Security (10 min)
**Goal**: Ensure type safety and security compliance

```bash
# Type checking
mypy app/ --ignore-missing-imports

# Security scanning
bandit -r app/ -f json

# Check for any critical security issues
```

**Expected Results**:
- Type annotations properly applied to all new model classes
- No security violations in enhanced response adapter
- Proper typing for all async service methods

## 🎯 Quality Standards Verification

### Code Quality Metrics
- **Line Length**: ≤100 characters (enforced by black)
- **Import Organization**: Proper grouping and sorting (enforced by isort)
- **Linting Violations**: <25 total violations (ruff target)
- **Type Coverage**: All public methods properly annotated
- **Security**: Zero critical violations (bandit)

### Enhanced Functionality Quality
- **NPO Model Classes**: Properly typed with clear docstrings
- **Response Adapter**: Clean helper method organization
- **Service Layer**: Proper async patterns and error handling
- **Test Infrastructure**: AsyncMock patterns properly implemented

## 🚨 Common Issues & Resolutions

### Formatting Issues
**Symptoms**: Black or isort failures
**Common Causes**: Line length violations, import conflicts
**Solutions**:
```bash
# Fix line length issues
black app/ tests/ --line-length=100 --force

# Resolve import conflicts
isort app/ tests/ --force-single-line --profile black
```

### Linting Violations
**Symptoms**: High ruff violation count (>25)
**Common Causes**: Complexity, unused imports, async patterns
**Solutions**:
1. **Complexity (C901)**: Extract complex methods into smaller functions
2. **Unused imports**: Remove or mark with `# noqa: F401` if needed for typing
3. **Async patterns**: Ensure proper AsyncMock usage in tests

### Type Checking Issues
**Symptoms**: mypy errors in new code
**Common Causes**: Missing type annotations, forward references
**Solutions**:
```bash
# Add missing type annotations to new model classes
# Use modern union syntax: str | None instead of Union[str, None]
# Add return type annotations to all public methods
```

### Security Violations
**Symptoms**: Bandit warnings/errors
**Common Causes**: Hardcoded secrets, insecure patterns
**Solutions**:
1. **Never hardcode API keys**: Use environment variables only
2. **Use secure hash functions**: SHA256+ for any hashing needs
3. **Proper exception handling**: Don't leak sensitive information

## ✅ Pre-commit Hook Simulation

### Test Hook Compliance
```bash
# Simulate the exact pre-commit hook sequence
black app/ tests/ --check --line-length=100 && \
isort app/ tests/ --check-only --profile black --line-length=100 && \
ruff check app/ tests/ && \
mypy app/ && \
bandit -r app/ -q

# Expected: All commands pass with exit code 0
```

**Success Criteria**:
- ✅ Black check passes (no formatting needed)
- ✅ Isort check passes (imports properly organized)
- ✅ Ruff passes with <25 violations
- ✅ Mypy passes without errors
- ✅ Bandit passes without critical violations

## 📊 Final Test Re-verification

### Ensure No Regressions
```bash
# Quick test run to ensure quality fixes didn't break anything
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" \
GOOGLE_API_KEY="fake-key-for-testing" \
python -m pytest tests/unit/ --tb=no -q --maxfail=5

# Expected: Same or better pass rate as Phase 3 (≤18 failures)
```

**Regression Check**:
- ✅ No new test failures introduced by formatting/linting fixes
- ✅ All service pattern fixes still working
- ✅ NPO functionality still intact
- ✅ Enhanced response adapter still functional

## 🎯 Staging Preparation

### Review Changes for Commit
```bash
# Check what will be committed
git status
git diff --cached  # If changes already staged
git diff  # If changes not yet staged

# Ensure only intended files included
git add app/  # Enhanced production code
git add tests/  # Fixed test files
git add requirements*.txt  # Any dependency updates (if any)

# Explicitly exclude cache/config files
# .cache/, __pycache__/, .idea/, .DS_Store should be gitignored
```

**Staging Verification**:
- ✅ All enhanced functionality files staged
- ✅ All fixed test files staged
- ✅ No cache or temporary files staged
- ✅ No local configuration files staged
- ✅ All changes align with enhancement goals

## ✅ Exit Criteria

### Must-Have Outcomes
- ✅ **All pre-commit hooks pass**: Black, isort, ruff, mypy, bandit
- ✅ **No test regressions**: Same or better pass rate maintained
- ✅ **Clean staging area**: Only intentional changes staged
- ✅ **Quality standards met**: All code meets production standards

### Quality Gates Passed
- Code formatting: 100% compliant
- Import organization: 100% compliant
- Linting: <25 violations acceptable threshold
- Type checking: Zero errors
- Security: No critical violations
- Test stability: No new failures introduced

## 🎯 Next Phase Transition

### Handoff to Phase 5 (Final Commit)
**Prerequisites Met**:
- ✅ All quality checks pass without `--no-verify` needed
- ✅ Test suite stability maintained at expected level
- ✅ All enhanced functionality preserved and quality-compliant
- ✅ Staging area contains only intended changes

**Deliverables**:
- ✅ Pre-commit hook compliance confirmed
- ✅ Final code quality metrics
- ✅ Staging area ready for commit
- ✅ Test stability confirmation

---

**🎯 Success Metric**: Natural pre-commit hook passage with zero compromises on enhanced functionality
