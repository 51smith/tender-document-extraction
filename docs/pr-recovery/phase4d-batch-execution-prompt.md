# Phase 4d - Single Document Dead Code Removal + Test Consolidation Execution Framework

## 🎯 **PHASE 4D MISSION: CLEAN ARCHITECTURE + CONSOLIDATED TESTING**

### **Systematic Approach**
**Objective**: Remove legacy single document processing dead code AND consolidate 26→17 test files (35% reduction)
**Crisis Status**: Problem worsened since documentation - Job Manager tests expanded from 2→6 files (200% increase)
**Quality Standard**: Maintain ≥85% coverage + 100% test pass rate + all 6 quality gates throughout

### **Phase 4d Execution Framework**
Execute systematic dead code removal and test consolidation through focused phases:
- **Phase 1**: ✅ Dead Code Removal - Remove NotImplementedError + clean type signatures
- **Phase 2**: ✅ Model Consistency - Update ExtractionJob model to batch-only
- **Phase 3A**: ✅ Job Manager Test Consolidation (6→1 files) - MOST COMPLEX
- **Phase 3B**: ✅ Gemini Service Test Consolidation (3→1 files)
- **Phase 3C**: ✅ Extraction Router Consolidation (2→1 files)
- **Phase 3D**: ✅ Health Router Consolidation (2→1 files)
- **Phase 3E**: ✅ Gap Analysis Rename (1 file)
- **Phase 4**: ✅ Real Processing Implementation - Replace TODO in extraction_worker.py
- **Phase 5**: ✅ Final Validation & Next Batch Preparation

**Reference Document**: `docs/pr-recovery/phase-4d-single-document-dead-code-removal.md` (Updated Analysis)

---

## 🚨 **CURRENT EXECUTION STATUS**

### **🔥 CRITICAL CRISIS: Problem Significantly Worsened Since Documentation**
**Test File Explosion**: 26 total files (vs documented 22) - **18% worse than planned**
**Job Manager Crisis**: **6 test files** requiring consolidation (vs planned 2) - **200% expansion**
**Dead Code Status**: ⚠️ **NO PROGRESS** - Both TODOs still exist at exact same locations
**Architecture Pollution**: All union types still present throughout job_manager.py

### **Current Reality Assessment:**
- **26→17 test files**: 35% reduction needed (vs planned 23% reduction)
- **Job Manager Impact**: 135+ tests across 6 files requiring architectural analysis
- **9 duplicate method names** in Job Manager requiring resolution
- **3 duplicate method names** in Gemini Service requiring resolution
- **Dead code unchanged**: job_manager.py:677-680, extraction_worker.py:865

---

## 📋 **PHASE 4D SUCCESS CRITERIA**

### **Phase 1 (Dead Code Removal):**
- [ ] **NotImplementedError removed**: Delete dead code branch at job_manager.py:677-680
- [ ] **Type signatures cleaned**: Remove all union types where batch-only appropriate
- [ ] **Runtime validation added**: Ensure only BatchExtractionRequest supported
- [ ] **Tests updated**: Convert single-document patterns to batch-of-1
- [ ] **All quality gates passing**: Pytest, MyPy, Ruff, Black, Bandit, Isort

### **Phase 2 (Model Consistency):**
- [ ] **ExtractionJob updated**: Remove union type from request field
- [ ] **Serialization working**: Validate all functionality intact
- [ ] **All quality gates passing**: Complete validation before proceeding

### **Phase 3A (Job Manager Consolidation - MOST CRITICAL):**
- [ ] **Architecture analysis completed**: 9 duplicate methods analyzed for compatibility
- [ ] **Merge strategy defined**: Decision framework applied systematically
- [ ] **6→1 consolidation executed**: All tests preserved with no regression
- [ ] **135+ tests consolidated**: Maintain coverage and functionality
- [ ] **All quality gates passing**: Critical validation after major consolidation

### **Phase 3B-3E (Other Consolidations):**
- [ ] **Gemini Service**: 3→1 files with architectural compatibility analysis
- [ ] **Extraction Router**: 2→1 files with testing approach analysis
- [ ] **Health Router**: 2→1 files with coverage strategy analysis
- [ ] **Gap Analysis**: Simple rename operation
- [ ] **All quality gates passing**: After each consolidation

### **Phase 4 (Real Processing):**
- [ ] **TODO replaced**: extraction_worker.py:865 implemented properly
- [ ] **Actual processing**: Real document processing not mock data
- [ ] **All quality gates passing**: Final implementation validation

### **Phase 5 (Final Validation):**
- [ ] **26→17 files achieved**: 35% test file reduction accomplished
- [ ] **≥85% coverage maintained**: Currently ~91% preserved throughout
- [ ] **759+ tests passing**: 100% pass rate maintained
- [ ] **Clean architecture**: No dead code, consistent type system
- [ ] **All quality gates passing**: Complete validation
- [ ] **Next batch prepared**: Prompt file updated for continuation

---

## 🔧 **PHASE 1: Dead Code Removal**

### **Objective**
Remove legacy single document processing dead code from job_manager.py and enforce batch-only processing architecture.

### **Current Dead Code Locations:**
- **job_manager.py:677-680** - NotImplementedError branch (CRITICAL)
- **job_manager.py multiple methods** - Union type signatures (TYPE POLLUTION)
- **extraction_worker.py:865** - Valid TODO requiring implementation

### **STEP 1: Remove NotImplementedError Branch**
**Target**: Lines 677-680 in `app/services/job_manager.py`

```bash
# First, examine the current dead code
grep -A 5 -B 5 "NotImplementedError" app/services/job_manager.py

# Verify this is truly dead code (never executed in batch-only architecture)
grep -r "DocumentExtractionRequest(" app/routers/ tests/integration/
```

**Implementation**:
1. Remove the entire `else` block containing NotImplementedError
2. Ensure the parent function properly handles only BatchExtractionRequest
3. Add runtime validation that rejects single document requests

### **STEP 2: Clean Type Signatures Throughout job_manager.py**
**Target**: All methods with union types `DocumentExtractionRequest | BatchExtractionRequest`

```bash
# Find all union type signatures in job_manager.py
grep -n "DocumentExtractionRequest.*BatchExtractionRequest" app/services/job_manager.py

# Expected locations:
# - create_extraction_job() - Line ~71
# - _enqueue_job() - Line ~137
# - _monitor_and_fallback_job() - Line ~206
# - _process_job_directly() - Line ~596
# - _process_batch_job() - Line ~606
```

**Implementation**:
1. Change all signatures from `DocumentExtractionRequest | BatchExtractionRequest` to `BatchExtractionRequest`
2. Remove DocumentExtractionRequest imports that are no longer needed
3. Update any type hints and docstrings

### **STEP 3: Add Runtime Validation for Batch-Only Processing**
**Target**: Key entry points in job_manager.py

**Implementation**:
```python
# Add validation in create_extraction_job()
if not isinstance(request, BatchExtractionRequest):
    raise ValueError("Only batch processing is supported. Single documents must be submitted as batch of 1.")

# Ensure this validation catches any edge cases
```

### **STEP 4: Update Affected Tests**
**Target**: Any tests creating standalone DocumentExtractionRequest jobs

```bash
# Find tests creating single document jobs
grep -r "DocumentExtractionRequest(" tests/unit/test_job_manager*.py

# Convert these to batch-of-1 pattern:
# OLD: DocumentExtractionRequest(...)
# NEW: BatchExtractionRequest(documents=[DocumentExtractionRequest(...)])
```

### **STEP 5: QUALITY GATE LOOP**
**MANDATORY: All quality gates must pass before proceeding to Phase 2**

**Step 5A: Run All 6 Quality Gates**
```bash
# 1. All tests must pass (maintain 759+ passing tests)
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --tb=line -q

# 2. Coverage must stay ≥85% (currently ~91%)
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --cov=app --cov-report=term-missing

# 3. Type checking must pass
mypy app/

# 4. Linting must be clean
ruff check app/ tests/

# 5. Code formatting must be correct
black app/ tests/ --check && isort app/ tests/ --check-only

# 6. Security check must pass
bandit -r app/
```

**Step 5B: If ANY Quality Gate Fails**
- **STOP immediately** - Do not proceed to Phase 2
- **Return to Steps 1-4** - Fix the root cause of the failure
- **Common fixes**:
  - Test failures: Fix broken test assertions or missing imports
  - Coverage drops: Add tests for uncovered code paths
  - Type errors: Fix type annotations or imports
  - Linting errors: Fix code style violations
  - Format errors: Run `black app/ tests/ && isort app/ tests/`
  - Security issues: Address bandit warnings

**Step 5C: After Fixes - Return to Step 5A**
- Re-run ALL 6 quality gates again
- Ensure complete compliance across all gates
- Do not proceed until ALL gates pass

**Step 5D: Only When ALL Gates Pass - Proceed to Phase 2**
- Mark Phase 1 as ✅ **COMPLETED**
- Document dead code removal success
- Begin Phase 2 with clean foundation

---

## 🔧 **PHASE 2: Model Consistency**

### **Objective**
Update ExtractionJob model to enforce batch-only architecture and ensure serialization compatibility.

### **STEP 1: Update ExtractionJob Model**
**Target**: `app/models/extraction.py` line ~315

```bash
# Examine current model definition
grep -A 10 -B 5 "class ExtractionJob" app/models/extraction.py

# Current problematic definition:
# request: DocumentExtractionRequest | BatchExtractionRequest
#
# Should become:
# request: BatchExtractionRequest
```

**Implementation**:
1. Change the union type to single BatchExtractionRequest type
2. Update any model documentation or comments
3. Ensure imports are still correct

### **STEP 2: Test Serialization/Deserialization**
**Target**: Ensure all existing functionality works with updated model

```bash
# Test model serialization
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -c "
from app.models.extraction import ExtractionJob, BatchExtractionRequest, DocumentExtractionRequest
from datetime import datetime

# Create test batch request
doc_req = DocumentExtractionRequest(content='test', filename='test.pdf')
batch_req = BatchExtractionRequest(documents=[doc_req])

# Test model creation and serialization
job = ExtractionJob(
    job_id='test-123',
    request=batch_req,
    status='pending',
    created_at=datetime.now()
)

print('Model creation successful')
print('Serialization test:', job.model_dump())
"
```

### **STEP 3: QUALITY GATE LOOP**
**MANDATORY: All quality gates must pass before proceeding to Phase 3A**

**Follow the same 5A/5B/5C/5D pattern as Phase 1:**
- **5A**: Run all 6 quality gates
- **5B**: If ANY fail → Return to Steps 1-2 to fix
- **5C**: After fixes → Return to 5A to re-test
- **5D**: Only when ALL pass → Proceed to Phase 3A

---

## 🔧 **PHASE 3A: Job Manager Test Consolidation** - 🔥 **MOST CRITICAL**

### **Objective**
Consolidate 6 Job Manager test files into 1 comprehensive test file using architecture-first decision framework.

### **Current Job Manager Test Files Crisis:**
- **`test_job_manager.py`** (18 tests) - Original comprehensive tests
- **`test_job_manager_refactored.py`** (30 tests) - Sub-function specific tests
- **`test_job_manager_async_operations.py`** (23 tests) - Async/timing edge cases
- **`test_job_manager_coverage_boost.py`** (21 tests) - Error conditions
- **`test_job_manager_lifecycle_edge_cases.py`** (20 tests) - Complex workflows
- **`test_job_manager_redis_integration.py`** (23 tests) - Redis-specific tests

**Total**: **135+ tests** requiring architectural analysis and merge decisions

### **STEP 1: Architecture Compatibility Analysis**
**Analyze each duplicate method name for architectural compatibility**

```bash
# Identify all duplicate test method names
echo "=== Finding Job Manager Duplicate Test Methods ==="
for file in tests/unit/test_job_manager*.py; do
    echo "--- $(basename $file) ---"
    grep "def test_" "$file" | sed "s/.*def test_/test_/" | sed "s/(.*//"
done | sort | uniq -d

# Expected duplicates to analyze:
# - test_cancel_job_already_completed
# - test_cleanup_old_jobs_skip_active_jobs
# - test_get_sync_connection
# - test_initialize_job_resources_with_files
# - test_validate_status_update_request_invalid_progress
# - And 4 others...
```

**For each duplicate method, determine:**
1. **Which version tests current job_manager.py architecture?**
2. **Are they testing same functionality with different approaches?**
3. **Are they testing different aspects of same method?**
4. **Which approach is more comprehensive/modern?**

### **STEP 2: Merge Strategy Analysis**
**Apply architecture-first decision framework systematically**

**Decision Framework Priority:**
1. **🔧 Architecture Compatibility (PRIMARY)** - Choose version that tests current code
2. **📊 Coverage Quality (SECONDARY)** - Add missing edge cases from other versions
3. **🧪 Test Quality (TERTIARY)** - Modernize with AsyncMock, proper fixtures

**For Job Manager specifically, analyze:**
- **Async vs Sync approaches**: Which matches current implementation?
- **Redis integration patterns**: Which mocking strategy is compatible?
- **Error handling approaches**: Which tests current error paths?
- **Mock vs real object usage**: Which approach fits current architecture?

### **STEP 3: Execute Consolidation Using Decision Framework**

**Base File Selection**: Use `test_job_manager.py` as foundation (most stable/original)

**Consolidation Process:**
1. **Keep base file intact** - Preserve original 18 tests as foundation
2. **Add non-duplicate tests** - Merge unique tests from other 5 files
3. **Resolve duplicates** - Use architecture-first framework for each of 9 duplicates
4. **Organize by test classes** - Group related functionality (async, Redis, lifecycle, etc.)
5. **Update imports and fixtures** - Ensure all dependencies resolved

**Expected Result**: Single `test_job_manager.py` with ~135 tests organized in logical test classes

### **STEP 4: Validate No Regression**
```bash
# Run the consolidated test file in isolation
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_job_manager.py -v

# Ensure coverage is maintained for job_manager.py
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_job_manager.py --cov=app/services/job_manager.py --cov-report=term-missing

# Run full test suite to ensure no integration issues
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --tb=line -q
```

### **STEP 5: QUALITY GATE LOOP**
**CRITICAL: This is the most complex consolidation - quality gates are essential**

**Follow the same 5A/5B/5C/5D pattern:**
- **5A**: Run all 6 quality gates (especially important after major consolidation)
- **5B**: If ANY fail → Return to Steps 1-4 to fix consolidation issues
- **5C**: After fixes → Return to 5A to re-test
- **5D**: Only when ALL pass → Proceed to Phase 3B

**Upon Success**: Delete the 5 consolidated files:
```bash
# Only when quality gates pass - remove consolidated files
rm tests/unit/test_job_manager_refactored.py
rm tests/unit/test_job_manager_async_operations.py
rm tests/unit/test_job_manager_coverage_boost.py
rm tests/unit/test_job_manager_lifecycle_edge_cases.py
rm tests/unit/test_job_manager_redis_integration.py
```

---

## 🔧 **PHASE 3B: Gemini Service Test Consolidation**

### **Objective**
Consolidate 3 Gemini Service test files into 1 comprehensive test file.

### **Current Gemini Service Test Files:**
- **`test_gemini_service.py`** (26 tests) - Basic functionality OR current architecture
- **`test_gemini_service_enhanced.py`** (44 tests) - Advanced error handling
- **`test_gemini_service_refactored.py`** (52 tests) - Sub-function testing

**Total**: **122 tests** with known architectural evolution (genai API vs LLM service abstraction)

### **STEP 1: Architecture Compatibility Analysis**
**Analyze the architectural differences between test versions**

```bash
# Examine the 3 known duplicate methods
echo "=== Gemini Service Duplicate Methods ==="
echo "test_client_initialization - Check internal structure differences"
echo "test_generate_content_success - Check API approach differences"
echo "test_mime_type_detection - Check implementation differences"

# Analyze which version tests current architecture
grep -A 10 "test_client_initialization" tests/unit/test_gemini_service*.py
```

**Key Analysis Points:**
1. **API Approach**: Direct genai API vs LLM service abstraction layer
2. **Internal Structure**: `._provider/.model` vs `._llm_service/.settings`
3. **Mocking Strategy**: Which mocking approach matches current implementation?
4. **Error Handling**: Which version tests current error paths?

### **STEP 2: Merge Strategy Analysis**
**Determine which version represents current gemini_service.py architecture**

**Expected Finding**: Enhanced version likely tests current LLM service abstraction

**Decision Process:**
1. Examine current `app/services/gemini_service.py` implementation
2. Determine which test version matches current code structure
3. Use compatible version as base
4. Merge comprehensive coverage from other versions

### **STEP 3: Execute Consolidation Using Decision Framework**
**Consolidate based on architecture compatibility findings**

1. **Select architecturally-compatible base**
2. **Merge unique tests** from non-base files
3. **Resolve 3 duplicate methods** using architecture-first priority
4. **Organize test classes** logically (basic, advanced, error handling)
5. **Update imports and mocking** for consistency

### **STEP 4: Validate No Regression**
```bash
# Test consolidated file
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_gemini_service.py -v

# Check gemini_service.py coverage
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_gemini_service.py --cov=app/services/gemini_service.py --cov-report=term-missing
```

### **STEP 5: QUALITY GATE LOOP**
**Follow same 5A/5B/5C/5D pattern - ALL gates must pass before Phase 3C**

**Upon Success**: Remove consolidated files:
```bash
rm tests/unit/test_gemini_service_enhanced.py
rm tests/unit/test_gemini_service_refactored.py
```

---

## 🔧 **PHASE 3C: Extraction Router Consolidation**

### **Objective**
Consolidate 2 Extraction Router test files into 1 comprehensive test file.

### **Current Files:**
- **`test_extraction_router.py`** (667 lines) - Full FastAPI integration tests
- **`test_extraction_router_simple.py`** (420 lines) - Direct function call tests

### **STEP 1: Architecture Compatibility Analysis**
**Determine testing approach differences**

```bash
# Analyze testing approaches
echo "=== Extraction Router Testing Approaches ==="
echo "Full integration vs Direct function calls"

# Check for duplicate method names
for file in tests/unit/test_extraction_router*.py; do
    echo "--- $(basename $file) ---"
    grep "def test_" "$file" | head -10
done
```

**Analysis Focus:**
1. **Testing Level**: FastAPI integration vs unit testing
2. **Mock Strategy**: Which approach tests current router implementation?
3. **Coverage Areas**: Are they complementary or overlapping?

### **STEP 2: Merge Strategy Analysis**
**Determine consolidation approach based on current router architecture**

**Decision Process:**
1. Which approach better tests current `app/routers/extraction.py`?
2. Are both approaches valuable or is one deprecated?
3. Can they be organized into complementary test classes?

### **STEP 3: Execute Consolidation**
**Merge based on architecture analysis results**

### **STEP 4: Validate No Regression**
```bash
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_extraction_router.py -v
```

### **STEP 5: QUALITY GATE LOOP**
**All gates must pass before Phase 3D**

---

## 🔧 **PHASE 3D: Health Router Consolidation**

### **Objective**
Consolidate 2 Health Router test files into 1 comprehensive test file.

### **Current Files:**
- **`test_health_router.py`** (917 lines) - Full integration tests
- **`test_health_router_coverage.py`** (264 lines) - Coverage-focused tests

### **STEP 1: Architecture Compatibility Analysis**
**Analyze integration vs coverage-focused approaches**

### **STEP 2: Merge Strategy Analysis**
**Determine if approaches are complementary or competing**

### **STEP 3: Execute Consolidation**
**Merge based on analysis**

### **STEP 4: Validate No Regression**
```bash
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_health_router.py -v
```

### **STEP 5: QUALITY GATE LOOP**
**All gates must pass before Phase 3E**

---

## 🔧 **PHASE 3E: Gap Analysis Rename**

### **Objective**
Simple rename operation - only one file exists.

### **STEP 1: Simple Rename Operation**
```bash
# Rename the file
mv tests/unit/test_gap_analysis_refactored.py tests/unit/test_gap_analysis.py

# Verify the renamed file works
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest tests/unit/test_gap_analysis.py -v
```

### **STEP 2: QUALITY GATE LOOP**
**All gates must pass before Phase 4**

---

## 🔧 **PHASE 4: Real Processing Implementation**

### **Objective**
Replace TODO in extraction_worker.py:865 with actual document processing implementation.

### **STEP 1: Replace TODO in extraction_worker.py:865**
**Target**: `_ = service  # TODO: Use service for actual document processing`

**Current Context Analysis**:
```bash
# Examine the current TODO location and context
grep -A 10 -B 10 "TODO.*service" app/services/extraction_worker.py

# This TODO is in _process_single_document() function
# This function IS used by batch processing for individual documents
```

### **STEP 2: Implement Actual Document Processing**
**Replace mock data with real processing using service parameter**

**Implementation**:
1. Use the `service` parameter for actual document processing
2. Get actual document content from file storage
3. Use `ExtractionService._process_document_content()` for real AI processing
4. Handle file retrieval errors properly
5. Maintain job progress updates

### **STEP 3: QUALITY GATE LOOP**
**All gates must pass before Phase 5**

---

## 🔧 **PHASE 5: Final Validation & Next Batch Preparation**

### **Objective**
Validate all Phase 4d objectives achieved and prepare for next development phase.

### **STEP 1: Verify All Objectives Met**
**Complete Phase 4d Success Validation**

```bash
# 1. Verify 26→17 file reduction achieved
echo "=== File Count Validation ==="
echo "Test files before: 26"
echo "Test files after: $(find tests/unit -name "test_*.py" | wc -l)"

# 2. Verify dead code removed
echo "=== Dead Code Validation ==="
echo "Checking for NotImplementedError..."
grep -r "NotImplementedError" app/services/job_manager.py || echo "✅ Dead code removed"

echo "Checking for union types..."
grep -r "DocumentExtractionRequest.*BatchExtractionRequest" app/services/job_manager.py || echo "✅ Types cleaned"

# 3. Verify test coverage maintained
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --cov=app --cov-report=term | grep "TOTAL"
```

### **STEP 2: Update Documentation**
**Document Phase 4d completion and achievements**

```bash
# Update the phase-4d document status
# Mark all phases as completed
# Document lessons learned and challenges overcome
```

### **STEP 3: Update Prompt File for Next Batch**
**Prepare this prompt file for next phase execution**

**Mark Phase 4d as COMPLETED:**
- Update status from "In Progress" to "✅ **COMPLETED**"
- Document final metrics: files reduced, coverage maintained, etc.
- Add completion timestamp and summary

**Prepare for Next Phase:**
- Review phase4e-batch-execution-prompt.md for next priorities
- Update any remaining batch targets
- Ensure clean handoff to subsequent development work

### **STEP 4: QUALITY GATE LOOP - FINAL VALIDATION**
**CRITICAL: Final quality gate validation before declaring Phase 4d complete**

**Step 4A: Final Quality Gate Run**
```bash
# All tests must pass - final validation
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --tb=line -q

# Coverage must be ≥85%
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --cov=app --cov-report=term-missing

# All 6 quality gates must pass
mypy app/ && ruff check app/ tests/ && black app/ tests/ --check && isort app/ tests/ --check-only && bandit -r app/
```

**Step 4B-4D: Follow Standard Quality Gate Loop**
- If ANY gate fails → Return to appropriate phase to fix
- Only when ALL gates pass → Declare Phase 4d COMPLETED

---

## ⚠️ **QUALITY GATE LOOP METHODOLOGY**

### **Universal Quality Gate Pattern (Used in Every Phase)**
**This pattern is LAW - followed identically in every phase Step 5 (or final step)**

### **Step A: Run All 6 Quality Gates**
```bash
# 1. Pytest - All tests must pass (maintain 759+ tests)
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --tb=line -q

# 2. Coverage - Must maintain ≥85% (currently ~91%)
SECRET_KEY="test-secret-key-that-is-definitely-more-than-32-characters-long-for-testing-purposes-only" GOOGLE_API_KEY="fake-key-for-testing" python -m pytest --cov=app --cov-report=term-missing

# 3. MyPy - Type checking must pass
mypy app/

# 4. Ruff - Linting must be clean
ruff check app/ tests/

# 5. Black & Isort - Formatting must be correct
black app/ tests/ --check && isort app/ tests/ --check-only

# 6. Bandit - Security check must pass
bandit -r app/
```

### **Step B: If ANY Quality Gate Fails**
**MANDATORY: STOP immediately and fix before proceeding**

**Common Failure Types & Fixes:**
- **Test Failures**: Fix broken assertions, imports, or test logic
- **Coverage Drops**: Add tests for uncovered code paths
- **Type Errors**: Fix type annotations, imports, or method signatures
- **Linting Errors**: Fix code style violations (unused vars, complexity, etc.)
- **Format Errors**: Run `black app/ tests/ && isort app/ tests/` to fix
- **Security Issues**: Address bandit warnings appropriately

**Fix Strategy:**
1. **Identify root cause** of the specific failure
2. **Return to appropriate implementation steps** in the current phase
3. **Make targeted fixes** without breaking other functionality
4. **Test fixes locally** before proceeding

### **Step C: After Fixes - Return to Step A**
**Re-run ALL 6 quality gates again**
- Do not skip any gates - must run complete validation
- Ensure fixes didn't break other quality aspects
- Continue loop until ALL gates pass

### **Step D: Only When ALL Gates Pass - Proceed**
**Gate passage is MANDATORY for phase progression**
- Mark current phase as ✅ **COMPLETED**
- Document any issues encountered and resolved
- Proceed to next phase with clean foundation

### **Critical Success Factors:**
- **No Shortcuts**: Never skip quality gate failures
- **Complete Validation**: Always run all 6 gates together
- **Fix Root Causes**: Don't suppress symptoms, fix underlying issues
- **Document Issues**: Track patterns for future improvement

---

## 🎯 **PHASE 4D COMPLETION CRITERIA**

### **Technical Achievement Requirements**
- [ ] **Dead Code Eliminated**: NotImplementedError removed, types cleaned
- [ ] **Model Consistency**: ExtractionJob updated to batch-only
- [ ] **Test Consolidation**: 26→17 files (35% reduction) with architecture compatibility
- [ ] **Real Processing**: TODO replaced with actual implementation
- [ ] **Quality Preserved**: ≥85% coverage + 100% test pass + all 6 quality gates

### **Architecture Requirements**
- [ ] **Batch-Only Processing**: No single document processing code paths
- [ ] **Clean Type System**: No union types where batch-only appropriate
- [ ] **Consistent Testing**: 1:1 mapping between source files and test files
- [ ] **No Regression**: All existing functionality preserved

### **Quality Gate Compliance**
- [ ] **Pytest**: 759+ tests passing (100% pass rate)
- [ ] **Coverage**: ≥85% maintained (currently ~91%)
- [ ] **MyPy**: 0 type errors
- [ ] **Ruff**: 0 linting violations
- [ ] **Black/Isort**: Perfect formatting
- [ ] **Bandit**: 0 security issues

### **Documentation & Handoff**
- [ ] **Phase Status Updated**: All phases marked as completed
- [ ] **Metrics Documented**: File reduction, coverage preservation, etc.
- [ ] **Next Phase Prepared**: Clean handoff to subsequent development

---

## 🚀 **EXECUTABLE PROMPT: PHASE 4D EXECUTION**

### **Claude, Execute the Following Systematic Phase 4d Implementation**

**MISSION**: Remove legacy single document dead code AND consolidate 26 test files to 17 files while maintaining ≥85% coverage + 100% test pass rate + all 6 quality gates.

**CRITICAL CRISIS CONTEXT**:
- **Problem worsened since documentation**: 26 files (vs planned 22)
- **Job Manager expansion**: 6 test files (vs planned 2) - 200% more complex
- **Dead code unchanged**: Both TODOs still exist at exact locations
- **Quality foundation required**: Must maintain strict standards throughout

### **EXECUTION SEQUENCE:**
1. **START with Phase 1**: Dead code removal with quality gate loop
2. **Proceed through phases systematically**: Never skip ahead
3. **Quality gate compliance is LAW**: ANY failure stops progress until fixed
4. **Architecture-first consolidation**: Use decision framework for all duplicates
5. **Complete validation**: Final quality gate loop before declaring success

**Success Declaration**: Only when ALL phases complete + ALL quality gates pass + 26→17 file reduction achieved + dead code eliminated.

**🚨 QUALITY GATE FAILURES = IMMEDIATE STOP + FIX + RETRY CYCLE**

### **Upon Successful Completion:**
Mark this prompt file as ✅ **PHASE 4D COMPLETED** and prepare for next development phase.
