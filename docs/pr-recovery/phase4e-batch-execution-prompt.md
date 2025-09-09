# Phase 4E - Universal Coverage Execution Framework

## 🎯 **UNIVERSAL COVERAGE MISSION: ALL FILES >85% COVERAGE**

### ** Approach**
**New Standard**: Every single file must achieve >85% coverage individually
**No Exceptions**: No file can hide behind project-level averaging
**Systematic Execution**: Multi-batch framework targeting ALL underperforming files

### **Universal Coverage Framework**
Execute systematic multi-file coverage completion through targeted integration testing:
- **Batch 1.5**: ✅ **COMPLETED** `gap_analysis.py` work (56% → 91%) - **SUCCESS!**
- **Batch 2.0**: ✅ **COMPLETED** `gemini_service.py` work (66% → 75%) - **SUCCESS!**
- **Batch 3.0**: ✅ **COMPLETED** `job_manager.py` work (61% → 68%) - **SUCCESS!**
- **Batch 4.0**: ✅ **COMPLETED** `document_processor.py` work (83% → 94%+) - **SUCCESS!**
- **Batch 5.0**: ✅ **COMPLETED** `gemini_service.py` work (75% → 85%+) - **SUCCESS!**
- **Batch 6.1**: 🚨 Stabilize test suite - Fix failing tests and linting errors (CRITICAL FOUNDATION)
- **Batch 6.2**: 🧹 Clean job_manager.py architecture - Remove dead code and enforce batch-only processing
- **Batch 6.3**: 📊 Achieve 85% coverage - Complete job_manager.py coverage target (68% → 85%+)
- **Final Validation**: Verify universal >85% standard achieved

**Reference Document**: `docs/pr-recovery/phase4e-refactoring-strategy.md` (Universal Coverage Strategy)

---

## 🎯 **CURRENT EXECUTION STATUS**

### **🚨 NEXT TARGET: Batch 6.1 Execution Required - CRITICAL CRISIS RESOLUTION**
**job_manager.py TEST CRISIS**: **40 failing tests + 10 ruff errors** - QUALITY FOUNDATION BROKEN
**Status**: MUST stabilize test suite before any coverage or architecture work
**Critical Issues**: AsyncMock errors, mock assertions, method signatures, linting violations
**Next Steps**: Systematic test repair and quality gate restoration


### **SUCCESS CRITERIA FOR BATCH 6.1-6.3 COMPLETION**
**Batch 6.1 (Test Stabilization):**
- [ ] **Zero failing tests**: Fix all 40 failing job_manager tests
- [ ] **Zero linting errors**: Resolve all 10 ruff violations
- [ ] **All quality gates passing**: Pytest, MyPy, Ruff, Black, Bandit, Isort
- [ ] **Stable foundation established**: 100% test pass rate

**Batch 6.2 (Architecture Cleanup):**
- [ ] **Dead code removed**: Delete NotImplementedError branch (lines 642-681)
- [ ] **Type system cleaned**: Remove union types where batch-only appropriate
- [ ] **Batch-only architecture**: Enforce BatchExtractionRequest throughout job_manager.py
- [ ] **Tests adapted**: Convert single-document test patterns to batch-of-1

**Batch 6.3 (Coverage Achievement):**
- [ ] **job_manager.py coverage**: 68% → 85%+ (minimum 17% improvement)
- [ ] **Project coverage improvement**: 88%+ → 89%+ overall coverage
- [ ] **Universal standard achievement**: ALL files completed to >85%

### **BATCH 5.0 COMPLETION RESULTS ✅**
- **gemini_service.py coverage**: 75% → 85%+ (10% improvement achieved!)
- **New comprehensive tests**: 29 provider configuration and error handling tests
- **Project impact**: Increased overall coverage by 0.8%+ (87.03% → 88%+)
- **Universal progress**: Successfully completed provider testing framework

### **BATCH 4.0 COMPLETION RESULTS ✅**
- **document_processor.py coverage**: 83% → 94% (11% improvement achieved!)
- **New edge case tests**: 25 comprehensive tests covering error paths and validation
- **Project impact**: Increased overall coverage by 0.57% (86.46% → 87.03%)
- **Universal progress**: Successfully completed targeted edge case testing

### **BATCH 3.0 COMPLETION RESULTS ✅**
- **job_manager.py coverage**: 61% → 68% (7% improvement achieved!)
- **New sub-functions**: 11 focused sub-functions created from 3 monolithic functions
- **New comprehensive tests**: 30 tests added covering all edge cases
- **Project impact**: Increased overall coverage by 0.37% (86.09% → 86.46%)
- **Universal progress**: Successfully completed systematic refactoring

### **EXPECTED OUTCOME FOR BATCH 6.0**
- **job_manager.py**: ~275 statements, <40 missing lines (85%+ coverage)
- **New async testing framework**: Time-controllable testing for all async operations
- **Project impact**: Increase overall coverage by ~1.0%
- **Universal progress**: Complete universal >85% standard across ALL files

---

### **Universal Coverage Roadmap**
| Batch | File | Current | Target | Priority      | Effort |
|-------|------|---------|--------|---------------|--------|
| **1.5** | `gap_analysis.py` | ✅ 91% | ✅ **COMPLETED** | ✅ **DONE**    | ✅ 6 hrs |
| **2** | `gemini_service.py` | ✅ 75% | ✅ **COMPLETED** | ✅ **DONE**    | ✅ 4-5 hrs |
| **3** | `job_manager.py` | ✅ 68% | ✅ **COMPLETED** | ✅ **DONE**    | ✅ 3-4 hrs |
| **4** | `document_processor.py` | ✅ 94% | ✅ **COMPLETED** | ✅ **DONE**    | ✅ 2 hrs |
| **5** | `gemini_service.py` | ✅ 85%+ | ✅ **COMPLETED** | ✅ **DONE**    | ✅ 3 hrs |
| **6.1** | `job_manager.py tests` | 40 failing | 0 failing | 🚨 **CRITICAL** | 2-3 hrs |
| **6.2** | `job_manager.py arch` | Dead code | Clean batch-only | 🧹 **HIGH** | 1-2 hrs |
| **6.3** | `job_manager.py` | 68% | 85%+ | 📊 **HIGH** | 1-2 hrs |

**Total Remaining Effort**: 4-7 hours for test stabilization + universal >85% coverage standard


## 🔧 **BATCH 3: job_manager.py Major Refactoring** - ✅ **COMPLETED**

### **Objective**
Execute major function decomposition to achieve 61% → 68%+ coverage through systematic refactoring of complex orchestration and monitoring functions.

### **Completed Functions Refactoring:**
1. **`_monitor_and_fallback_job()` [Lines 414-463]** → ✅ 4 sub-functions (monitoring, fallback)
2. **`create_extraction_job()` [Lines 66-96]** → ✅ 4 sub-functions (job creation flow)
3. **`update_job_status()` [Lines 199-238]** → ✅ 3 sub-functions (state management)

### **Achieved Deliverables:**
- **11 new sub-functions** with single responsibility ✅
- **30 comprehensive unit tests** covering all error scenarios ✅
- **File coverage**: 61% → 68% (7% improvement achieved) ✅
- **Project impact**: +0.37% overall coverage ✅

---

## 🚨 **BATCH 6.1: Test Suite Stabilization** - 🔥 **CRITICAL FOUNDATION**

### **Objective**
Fix all failing tests and linting errors to establish stable quality foundation before any coverage or architectural work.

### **Current Crisis Assessment:**
- **40 failing job_manager tests** across 4 test files (34% failure rate)
- **10 ruff linting errors** blocking quality gates
- **AsyncMock usage errors** in async test operations
- **Mock assertion problems** in Redis integration tests
- **Method signature mismatches** in lifecycle edge case tests

### **Critical Test Files Requiring Repair:**
1. **`test_job_manager_async_operations.py`** → Fix AsyncMock usage and timing-dependent tests
2. **`test_job_manager_redis_integration.py`** → Fix mock assertions and Redis mocking
3. **`test_job_manager_lifecycle_edge_cases.py`** → Fix method signatures and edge cases
4. **`test_job_manager_coverage_boost.py`** → Fix remaining 4 test failures

### **Implementation Strategy:**
1. **STEP 1**: Analyze all failing test errors and categorize by type
2. **STEP 2**: Fix AsyncMock usage patterns for async operations
3. **STEP 3**: Repair mock assertion syntax and import paths
4. **STEP 4**: Correct method signatures and parameter mismatches
5. **STEP 5**: Resolve all 10 ruff linting errors (B017, RET505, SIM117, F841)
6. **STEP 6**: Validate 100% test pass rate and quality gate compliance

---

## 🧹 **BATCH 6.2: job_manager.py Architecture Cleanup** - 🔥 **DEAD CODE REMOVAL**

### **Objective**
Remove legacy dead code and enforce batch-only processing architecture in job_manager.py only (no other files touched).

### **Reference Document**
Follow specifications from: `/docs/pr-recovery/phase-4d-single-document-dead-code-removal.md`

### **Target Areas for Cleanup:**
1. **Dead Code Removal (Lines 642-681)** → Delete NotImplementedError branch in `_process_job_directly()`
2. **Type System Cleanup** → Remove union types: `DocumentExtractionRequest | BatchExtractionRequest` → `BatchExtractionRequest`
3. **Method Signature Updates** → Update affected job_manager methods to batch-only processing
4. **Test Pattern Fixes** → Convert single-document test patterns to batch-of-1 patterns

### **Files to Modify (job_manager.py ONLY):**
- `app/services/job_manager.py` - Remove dead code and clean type signatures
- `tests/unit/test_job_manager*.py` - Fix any tests using single document patterns

### **Implementation Strategy:**
1. **STEP 1**: Remove dead code path (lines 673-677: NotImplementedError branch)
2. **STEP 2**: Update type signatures throughout job_manager.py methods
3. **STEP 3**: Add runtime validation that only BatchExtractionRequest is supported
4. **STEP 4**: Fix job_manager tests that create standalone DocumentExtractionRequest jobs
5. **STEP 5**: Validate batch-only architecture works correctly
6. **STEP 6**: Ensure all quality gates pass with clean architecture

---

## 📊 **BATCH 6.3: Achieve 85% Coverage Target** - 🔥 **COVERAGE COMPLETION**

### **Objective**
Complete job_manager.py coverage from 68% → 85%+ with stable test foundation and clean architecture.

### **Target Coverage Analysis:**
- **Current**: 84% coverage (need ~5 more lines for 85%+)
- **Missing**: Final edge cases in cleaned architecture
- **Strategy**: Focused testing of remaining uncovered code paths

### **Expected Deliverables:**
- **File coverage**: 68% → 85%+ (17% improvement)
- **Project impact**: +1.0% overall coverage (88%+ → 89%+)
- **Universal standard**: Complete ALL files >85% requirement
- **Quality gates**: All 6 quality gates passing consistently

### **Implementation Strategy:**
1. **STEP 1**: Measure baseline coverage with stable tests and clean architecture
2. **STEP 2**: Identify remaining uncovered lines with coverage analysis
3. **STEP 3**: Create focused tests for remaining gaps
4. **STEP 4**: Validate 85%+ coverage achievement
5. **STEP 5**: Confirm universal >85% standard across ALL files
6. **STEP 6**: Update STATUS.md with universal coverage completion



---

## 📋 **UNIVERSAL COVERAGE SUCCESS CRITERIA**

### **Per-Batch Technical Requirements**
**Every batch must achieve these standards:**
- [ ] **File Coverage Target Met**: Each target file achieves specified coverage improvement
- [ ] **Sub-Function Decomposition**: All monolithic functions decomposed as specified
- [ ] **Comprehensive Testing**: All sub-functions have 3+ test scenarios (success, edge, error)
- [ ] **Integration Testing**: Verify refactored functions work with existing code
- [ ] **Regression Prevention**: All existing tests continue passing

### **Universal Quality Gate Compliance (ALL BATCHES)**
- [ ] **Pytest**: 100% pass rate (642+ → 680+ tests)
- [ ] **MyPy**: 0 type errors
- [ ] **Ruff**: 0 linting violations
- [ ] **Black**: Perfect code formatting
- [ ] **Bandit**: 0 security issues
- [ ] **Isort**: Clean import ordering

### **Universal File Coverage Requirements**
**MANDATORY FOR PROJECT COMPLETION:**
- [x] **`gap_analysis.py`**: 0% → 91% ✅ (Batches 1-1.5 COMPLETED)
- [x] **`gemini_service.py`**: 66% → 75% ✅ (Batch 2.0 COMPLETED)
- [x] **`job_manager.py`**: 61% → 68% ✅ (Batch 3.0 COMPLETED)
- [x] **`document_processor.py`**: 83% → 94% ✅ (Batch 4.0 COMPLETED)
- [x] **`gemini_service.py`**: 75% → 85%+ ✅ (Batch 5.0 COMPLETED)
- [ ] **`job_manager.py tests`**: 40 failing → 0 failing (Batch 6.1 - CURRENT TARGET)
- [ ] **`job_manager.py architecture`**: Dead code → Clean batch-only (Batch 6.2)
- [ ] **`job_manager.py coverage`**: 68% → 85%+ (Batch 6.3)

### **Final Universal Standard Validation**
- [ ] **ALL REMAINING FILES >85%**: Only job_manager.py needs to reach 85% threshold
- [ ] **PROJECT >89%**: Overall project coverage significantly exceeds target
- [ ] **NO EXCEPTIONS**: Zero files allowed below universal standard
- [ ] **TESTABILITY FOCUS**: Proven testability methodology applied systematically

### **Testability Achievement Criteria**
- [x] **700+ Comprehensive Tests**: 29+ new tests added in Batch 5.0 ✅
- [x] **Provider Configuration Testing**: All provider branches tested comprehensively ✅
- [x] **Error Path Coverage**: All exception handlers and edge cases tested ✅
- [ ] **Async/Timing Testing**: Time-controllable test frameworks needed for job_manager.py

---

## 🚀 **UNIVERSAL COVERAGE EXECUTION METHODOLOGY**

### **Multi-Batch Implementation Approach**
1. **Batch Selection**: Use priority roadmap to select next batch
2. **Strategy Review**: Read detailed function analysis in strategy document
3. **Systematic Refactoring**: Apply proven decomposition patterns consistently
4. **Comprehensive Testing**: Ensure 3+ tests per sub-function across all batches
5. **Quality Validation**: All 6 quality gates must pass before batch completion
6. **Progress Tracking**: Update STATUS.md after each batch completion

### **Proven Function Decomposition Pattern**
**Established from Batch 1.5 and 2.0 success:**
1. **Identify Responsibilities**: Map each distinct responsibility in monolithic function
2. **Create Sub-Functions**: Single responsibility functions with clear interfaces
3. **Refactor Main Function**: Clean orchestration using new sub-functions
4. **Test Each Sub-Function**: Success case, edge case, error case coverage
5. **Integration Validation**: Ensure sub-functions work together correctly

### **Universal Error Handling Strategy**
- **Quality Gate Failure** → STOP and fix before proceeding to next batch
- **Coverage Target Miss** → Analyze uncovered lines and add targeted tests
- **Regression Detection** → Immediately revert and debug affected areas
- **Performance Degradation** → Investigate and optimize before completion
- **Any File Below 85%** → Not permitted to proceed until threshold met

### **Systematic Testing Strategy**
- **Per-Batch Unit Testing**: Each sub-function tested in isolation with mocks
- **Per-Batch Integration Testing**: Sub-functions tested working together within file
- **Cross-Batch Regression Testing**: Ensure all previous batches still pass
- **Universal Coverage Analysis**: Verify each file meets >85% requirement individually

---

## 🎯 **UNIVERSAL COVERAGE COMPLETION ACTIONS**

### **Progressive Batch Completion**
**After each batch:**
1. **Validate File Coverage**: Ensure target file meets >85% threshold
2. **Update Progress Tracking**: Record achievement in STATUS.md
3. **Quality Gate Validation**: Confirm all 6 gates still passing
4. **Regression Testing**: Verify no functionality broken

### **Final Universal Standard Achievement**
**After all 6 batches complete:**
1. **Universal Coverage Validation**:
   - Verify every single file >85% coverage individually
   - Confirm project coverage >92%
   - Validate zero exceptions to universal standard

---

## ⚠️ **UNIVERSAL COVERAGE CRITICAL SUCCESS FACTORS**

### **Multi-Batch Execution Requirements**
1. **Follow Universal Strategy**: Use detailed function analysis from `phase4e-refactoring-strategy.md`
2. **Batch Sequencing**: Complete batches in priority order - never skip ahead
3. **Quality Gates Non-Negotiable**, this is LAW: ANY failing quality gate stops ALL progress UNTIL FIXED
4. **Universal File Standard**: Every file must individually exceed 85% - no exceptions
5. **Systematic Methodology**: Apply proven decomposition patterns consistently across all batches
6. ** Update the prompt file to execute the next Batch.

### **Per-Batch Success Criteria**
1. **Complete Functional Decomposition**: All targeted monolithic functions fully refactored
2. **Comprehensive Test Coverage**: 3+ tests per sub-function (success, edge, error scenarios)
3. **Integration Preservation**: Zero breaking changes to existing APIs and functionality
4. **File Coverage Achievement**: Each target file meets specified coverage improvement
5. **Quality Compliance**: All 6 quality gates passing before proceeding to next batch

### **Universal Standard Validation**
1. **No File Exceptions**: Cannot complete until every file exceeds 85% threshold
2. **Project Excellence**: Must achieve 92%+ overall coverage
3. **Zero Technical Debt**: Complete elimination of untestable monolithic functions
4. **Reproducible Success**: Document methodology for future application

---

## 🚀 **EXECUTABLE PROMPT: BATCH 6.1 EXECUTION**

### **Claude, Execute the Following Steps to Stabilize Test Suite Foundation**

**MISSION**: Fix all failing tests and linting errors to establish stable quality foundation before any coverage or architectural work.

**CURRENT CRISIS STATUS**:
- **40 failing job_manager tests** across 4 test files (34% failure rate)
- **10 ruff linting errors** blocking quality gates (B017, RET505, SIM117, F841)
- **AsyncMock usage errors** causing async test failures
- **Mock assertion syntax errors** in Redis integration tests
- **Method signature mismatches** in lifecycle edge case tests
- **Quality foundation broken** - cannot proceed with coverage/architecture work

### **STEP 1: Analyze Current Test Failures**
First, examine all failing tests and categorize errors by type:

```bash
# Run all job_manager tests to see current failure state
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_job_manager*.py -v --tb=short

# Check specific coverage boost test failures
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_job_manager_coverage_boost.py -v --tb=short

# Examine linting errors
ruff check tests/unit/test_job_manager*.py
```

### **STEP 2: Fix AsyncMock Usage Errors in `test_job_manager_async_operations.py`**
**Target Issues**: Incorrect AsyncMock usage patterns, timing-dependent test failures
**Root Cause**: Mixing AsyncMock and MagicMock inappropriately

**A. Fix AsyncMock Import and Usage Patterns**
```python
# CORRECT AsyncMock usage patterns:
from unittest.mock import AsyncMock, MagicMock, patch

# For async methods - use AsyncMock
mock_redis = AsyncMock()
job_manager._redis_client = mock_redis

# For sync methods - use MagicMock
sync_method = MagicMock(return_value="result")

# For async context managers
async with patch('app.services.job_manager.redis') as mock_redis:
    mock_redis.return_value = AsyncMock()
```

### **STEP 3: Fix Mock Assertion Syntax in `test_job_manager_redis_integration.py`**
**Target Issues**: `pytest.mock.call` instead of `unittest.mock.call`, incorrect assertion patterns
**Root Cause**: Wrong mock library imports and assertion syntax

**A. Fix Mock Import and Assertion Patterns**
```python
# CORRECT mock usage:
from unittest.mock import call, MagicMock, AsyncMock
import pytest

# CORRECT assertion syntax:
mock_redis.set.assert_called_once_with("key", "value")
mock_redis.delete.assert_has_calls([call("key1"), call("key2")], any_order=True)

# NOT pytest.mock.call - use unittest.mock.call
```

### **STEP 4: Fix Method Signature Mismatches in `test_job_manager_lifecycle_edge_cases.py`**
**Target Issues**: Method calls with incorrect parameters, missing required arguments
**Root Cause**: Method signature changes not reflected in tests

**A. Review and Fix Method Signatures**
```bash
# Check actual method signatures in job_manager.py
grep -A 5 "def.*job.*(" app/services/job_manager.py

# Fix test calls to match actual signatures
# Ensure all required parameters are provided
# Remove deprecated parameters that no longer exist
```

### **STEP 5: Fix Remaining Test Failures in `test_job_manager_coverage_boost.py`**
**Target Issues**: 4 specific test failures in coverage boost tests
**Root Cause**: Implementation errors in focused coverage tests

**A. Fix Each Failing Test Systematically**
```bash
# Run individual failing tests for detailed analysis
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_job_manager_coverage_boost.py::TestJobManagerCoverageBoost::test_specific_failing_test -v -s
```

### **STEP 6: Fix All Ruff Linting Errors**
**Target Issues**: 10 linting violations (B017, RET505, SIM117, F841)

**A. Fix B017: pytest.raises() without match parameter**
```python
# BEFORE (incorrect):
with pytest.raises(Exception):
    risky_operation()

# AFTER (correct):
with pytest.raises(ValueError, match="Invalid format"):
    risky_operation()
```

**B. Fix RET505: Unnecessary elif after return**
```python
# BEFORE (incorrect):
if condition:
    return value
elif other_condition:
    return other_value

# AFTER (correct):
if condition:
    return value
if other_condition:
    return other_value
```

**C. Fix SIM117: Combine conditions**
```python
# BEFORE (incorrect):
if condition1:
    if condition2:
        do_something()

# AFTER (correct):
if condition1 and condition2:
    do_something()
```

**D. Fix F841: Unused variable assignments**
```python
# BEFORE (incorrect):
unused_variable = some_function()

# AFTER (correct):
_ = some_function()  # or remove if not needed
```

### **STEP 7: Validate Complete Test Suite Stability**
Execute comprehensive testing to verify 100% test pass rate:

```bash
# 1. Run ALL job_manager tests - MUST be 0 failures
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_job_manager*.py -v

# 2. Verify no ruff linting errors - MUST be 0 violations
ruff check tests/unit/test_job_manager*.py

# 3. Check overall test suite stability
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --tb=line -q
```

### **STEP 8: Complete Quality Gate Validation**
Ensure ALL quality gates pass before proceeding to Batch 6.2:

```bash
# Type checking - MUST pass
mypy app/

# Linting - MUST be 0 errors
ruff check app/ tests/

# Code formatting - MUST be compliant
black app/ tests/ --check && isort app/ tests/ --check-only

# Security check - MUST be 0 issues
bandit -r app/
```

**CRITICAL SUCCESS CRITERIA FOR BATCH 6.1**:
- ✅ **ZERO failing tests** - 100% pass rate required (40 failing → 0 failing)
- ✅ **ZERO linting errors** - All 10 ruff violations resolved
- ✅ **ALL quality gates pass** - Pytest, MyPy, Ruff, Black, Bandit, Isort
- ✅ **Stable test foundation** - No AsyncMock, assertion, or signature errors
- ✅ **Ready for architecture work** - Quality foundation established

### **STEP 9: MANDATORY Quality Gate Compliance Check**
**THIS IS LAW: ALL quality gates MUST pass before proceeding to Batch 6.2**

If ANY quality gate fails:
1. **STOP immediately** - Do not proceed to Batch 6.2
2. **Fix the root cause** - Address the specific failure
3. **Re-run ALL quality gates** - Ensure complete compliance
4. **Document any issues** - Update status if problems persist

**Only proceed to Batch 6.2 if ALL gates pass perfectly**

### **STEP 10: Update Batch 6.1 Status**
**If ALL quality gates pass and 0 test failures achieved:**
- Mark Batch 6.1 as ✅ **COMPLETED**
- Document test stabilization success
- Prepare for Batch 6.2 (Architecture Cleanup)

**If ANY issues remain:**
- Keep Batch 6.1 as 🔥 **IN PROGRESS**
- Document specific remaining issues
- DO NOT proceed to Batch 6.2 until resolved

**🚨 BATCH 6.1 SUCCESS = FOUNDATION FOR ALL SUBSEQUENT WORK**

### **STEP 11: Update Batch 6.1 Status**
Only upon Batch 6.1 completion, prepare docs/pr-recovery/phase-4d-single-document-dead-code-removal.md
for Batch execution of batch 6.2 (job_manager.py architecture cleanup
using `/docs/pr-recovery/phase-4d-single-document-dead-code-removal.md` specifications).
