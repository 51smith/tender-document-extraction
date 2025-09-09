# Test Debugging & Best Practices Guide

This document captures key learnings from debugging test failures and implementing proper test practices in the Tender Document Extraction project.

## 🚨 Critical Lessons Learned

### 1. Never Bypass Validation Systems
**❌ Wrong Approach:**
```bash
git commit --no-verify  # Bypass pre-commit hooks
pytest --ignore=failing_tests/  # Skip failing tests
```

**✅ Correct Approach:**
- Always investigate and fix the root cause
- Pre-commit hooks exist for a reason - they prevent broken code from entering the codebase
- Failing tests indicate real issues that need addressing

**Real Example from this project:**
- Issue: Pre-commit hooks failing with `python_venv` error
- Wrong: Bypass with `--no-verify`
- Right: Investigate and fix the pre-commit cache issue

### 2. Fix Root Causes, Not Symptoms

**Example: Pre-commit python_venv Issue**
- **Symptom:** `InvalidManifestError: Expected one of... but got: 'python_venv'`
- **Surface fix:** Disable pre-commit hooks
- **Root cause:** Stale cache in `/Users/.cache/pre-commit/` with deprecated language setting
- **Proper solution:** `pre-commit clean && pre-commit install --install-hooks`

### 3. Async Testing Requires AsyncMock

**❌ Common Mistake:**
```python
# This will fail for async methods
mock_redis = MagicMock()
mock_redis.ping.return_value = True
# Error: object MagicMock can't be used in 'await' expression
```

**✅ Correct Pattern:**
```python
# Use AsyncMock for async operations
mock_redis = AsyncMock(spec=Redis)
mock_redis.ping = AsyncMock(return_value=True)
mock_redis.close = AsyncMock()
```

### 4. Systematic vs. One-off Fixes

**❌ One-off fixes:** Fix each test individually
**✅ Systematic approach:** Fix the fixture/pattern once, fix many tests

**Example:**
- Fixed `mock_redis` fixture in usage tracker tests
- Result: 40 tests fixed with one fixture improvement

## 🛠 Test Debugging Methodology

### Step 1: Categorize Failures
When you have many failing tests, group them by error pattern:

```bash
# Get failure summary
pytest --tb=no -q

# Analyze patterns
grep -r "AttributeError.*MagicMock.*await" tests/
grep -r "object has no attribute 'encode'" tests/
```

### Step 2: Fix Infrastructure First
1. **Pre-commit issues** - Fix before code issues
2. **Fixture problems** - Fix shared test utilities
3. **Import/dependency issues** - Fix module loading
4. **Individual test logic** - Fix last

### Step 3: Test the Fix Pattern
```bash
# Test one representative failure
pytest path/to/failing_test.py::specific_test -v

# If fixed, test the whole module
pytest path/to/failing_test.py -v

# Finally test related modules
pytest tests/unit/ -k "similar_pattern"
```

## 📋 Common Test Patterns & Solutions

### AsyncMock Configuration for Redis
```python
@pytest.fixture()
def mock_redis(self):
    """Properly configured Redis mock."""
    mock = AsyncMock(spec=Redis)
    # Configure all async methods your code uses
    mock.ping = AsyncMock(return_value=True)
    mock.close = AsyncMock()
    mock.set = AsyncMock()
    mock.get = AsyncMock()
    mock.hget = AsyncMock()
    mock.hgetall = AsyncMock(return_value={})
    mock.pipeline = AsyncMock(return_value=AsyncMock())  # Pipeline returns mock too
    return mock
```

### Template Response Mocking
```python
@pytest.fixture()
def mock_templates(self):
    """Mock Jinja2Templates to avoid file dependencies."""
    with patch("app.routers.web.templates") as mock_templates:
        from fastapi.responses import HTMLResponse
        mock_templates.TemplateResponse = MagicMock(
            return_value=HTMLResponse(content="<html>Mock</html>")
        )
        yield mock_templates
```

### Dependency Injection in Tests
```python
def test_with_dependency_override(self, sync_client):
    """Use FastAPI's dependency override system."""
    from app.dependencies import get_service
    import main

    mock_service = AsyncMock()
    main.app.dependency_overrides[get_service] = lambda: mock_service

    try:
        response = sync_client.post("/endpoint")
        # Test assertions
    finally:
        main.app.dependency_overrides.clear()
```

## 🔍 Debugging Specific Error Patterns

### "MagicMock can't be used in 'await' expression"
- **Cause:** Using `MagicMock` instead of `AsyncMock` for async methods
- **Fix:** Replace with `AsyncMock` and configure async methods
- **Check:** Ensure all awaited methods are `AsyncMock` instances

### "'dict' object has no attribute 'encode'"
- **Cause:** Template system returning dict instead of HTML response
- **Fix:** Mock `TemplateResponse` to return proper `HTMLResponse`
- **Check:** Verify template mocking is active in test

### "Expected 'X' to have been called"
- **Cause:** Mock not being called or wrong mock being checked
- **Fix:** Verify mock setup and call path
- **Debug:** Add `print(mock.call_args_list)` to see actual calls

## 📊 Test Quality Metrics

Track these metrics to maintain test health:

```bash
# Pass rate
pytest --tb=no | grep -E "(failed|passed)"

# Coverage by module
pytest --cov=app --cov-report=term-missing

# Test speed
pytest --durations=10
```

**Quality Targets:**
- Pass rate: >95%
- Coverage: >85% (as per project config)
- No flaky tests (consistent results)
- Fast feedback (<2 min for unit tests)

## 🚦 Pre-commit Hook Debugging

### Common Issues:
1. **python_venv deprecated:** Clean cache and reinstall hooks
2. **Module import errors:** Check Python path and dependencies
3. **File formatting:** Let hooks auto-fix, then commit again

### Debug Commands:
```bash
# Check hook configuration
pre-commit validate-config

# Run specific hook
pre-commit run black --all-files

# Clean and reinstall
pre-commit clean
pre-commit install --install-hooks

# Check cache
ls ~/.cache/pre-commit/
```

## 📝 Documentation & Communication

### Commit Message Pattern:
```
fix: Major test suite improvements and async mocking fixes

SPECIFIC MODULE (Impact level):
- Specific change made
- Result/metrics

OVERALL IMPACT:
- High-level improvements
- Foundation for future work
```

### Code Review Checklist:
- [ ] All tests pass
- [ ] Pre-commit hooks pass
- [ ] Test coverage maintained/improved
- [ ] No bypassed validation
- [ ] Root causes addressed, not symptoms

## 🎯 Prevention Strategies

1. **TDD Approach:** Write tests first, avoid retrofitting fixes
2. **CI/CD Integration:** Run full test suite on every push
3. **Regular Maintenance:** Update dependencies and test frameworks
4. **Knowledge Sharing:** Document patterns and common issues
5. **Code Reviews:** Require test validation before merge

---

*Generated from debugging session on 2025-08-29*
*Last updated: [Auto-update on next major debugging session]*
