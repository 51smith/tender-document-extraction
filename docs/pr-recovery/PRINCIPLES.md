# 🏛️ PR Recovery Core Principles & Rules

**Foundation**: All decision-making must follow these absolute principles

## 🔥 CORE PRINCIPLE: NEVER REVERT TO OLD CODE
**Absolute Rule**: All new functionality must be preserved. If there are issues with the new enhanced code, we fix the new code forward. We DO NOT fall back to previous versions under any circumstances.

### 🎯 What We're Keeping (Non-Negotiable)
- ✅ **ALL new NPO transformation functionality** in response adapter
- ✅ **ALL new model classes**: `ProcurementPhase`, `ComplaintProcedure`, `DocumentStructure`
- ✅ **ALL enhanced response adapter helper methods** (`_extract_project_title`, `_extract_tender_documents`, etc.)
- ✅ **ALL improved error handling and logging** across services
- ✅ **ALL enhanced extraction worker** with provider fallback logic
- ✅ **ALL 24 NPO transformation tests** (they were passing before infrastructure issues)
- ✅ **ALL coverage improvements** and test enhancements
- ✅ **ALL multi-LLM architecture** enhancements

## ⚠️ Absolutely Forbidden Actions

### 🚫 NEVER DO THESE THINGS
- **NO reverting to old code versions** under any circumstances
- **NO removing enhanced functionality** to "fix" issues
- **NO `git commit --no-verify`** - hooks must pass naturally
- **NO half-measures** - fix issues completely or not at all
- **NO multiple commits** for what should be one comprehensive enhancement
- **NO bypassing quality gates** - if something fails, fix the root cause
- **NO removing tests** that were previously working
- **NO simplifying complex logic** back to old patterns

### ⛔ Emergency Scenarios (Still NO Exceptions)
Even if we encounter:
- Difficult-to-debug async mocking issues → **Fix the mocking, don't remove async**
- Complex service dependency problems → **Fix the dependencies, don't simplify**
- Time pressure to deliver → **Fix forward systematically, don't cut corners**
- Pre-commit hooks failing → **Fix the specific issues, don't bypass**

## 🎯 Required Discipline & Approach

### ✅ ALWAYS DO THESE THINGS
- **Fix forward only**: If new code has issues, fix the new code
- **One service at a time**: Complete each service pattern before moving to next
- **Verify each step**: Test after each pattern application
- **Preserve all enhancements**: Every new feature must be maintained
- **Root cause fixes**: Address underlying issues, not symptoms
- **Pattern-based solutions**: Use proven templates and systematic approaches
- **Quality-first**: Ensure all changes meet production standards

### 🔧 Problem-Solving Methodology
1. **Identify the pattern**: What type of issue is this? (Redis, HTTP, FastAPI, etc.)
2. **Find the template**: Do we have a proven solution for this pattern?
3. **Apply systematically**: Use the established template with service-specific adaptations
4. **Verify completely**: Ensure the fix works and doesn't break other functionality
5. **Document the pattern**: If it's new, add it to SERVICE-PATTERNS.md for reuse

## 🏆 Success Criteria (Non-Negotiable)

### Must-Have Outcomes
- ✅ **ALL new functionality preserved**: No rollbacks to old code
- ✅ **ZERO syntax errors**: All Python files must parse correctly
- ✅ **Test collection works**: `pytest --collect-only` succeeds (425 tests discovered)
- 🎯 **ALL UNIT TESTS PASS**: 425/425 tests must pass (currently 349/425 pass)
- 🎯 **Pre-commit hooks pass**: NO bypassing allowed
- 🎯 **Single clean commit**: Replace multi-commit chain with one comprehensive commit
- ✅ **Clean repository**: No cache files, config files, or merge artifacts
- ✅ **NPO functionality intact**: All 24 NPO transformation tests must be preserved

### Quality Gates That Must Pass
- All enhanced response adapter functionality must work
- All new model classes must be properly integrated
- Test infrastructure must be fully functional
- Coverage should be maintained or improved from current baseline
- No breaking changes to existing API contracts
- All service mocking must use proper AsyncMock patterns
- All error handling must be production-ready

## 🚨 Escalation Protocol

### When Stuck (Follow This Order)
1. **Check SERVICE-PATTERNS.md**: Is there an existing pattern for this issue?
2. **Analyze successful fixes**: How did we solve similar problems?
3. **Apply systematic debugging**: Use the established methodology
4. **Document new patterns**: If you discover a new solution, document it
5. **Never compromise principles**: If unsure, choose the path that preserves functionality

### Red Flags (Stop and Reassess)
- 🚩 **Considering removing functionality**: This violates core principles
- 🚩 **Wanting to bypass quality checks**: Fix the issue, don't bypass
- 🚩 **Thinking "just this once"**: There are no exceptions to these rules
- 🚩 **Feeling time pressure**: Quality and completeness are non-negotiable

## 📋 Quality Standards

### Code Quality Requirements
- All async operations must use AsyncMock, not MagicMock
- All service dependencies must be properly mocked
- All error paths must be tested
- All new patterns must be documented in SERVICE-PATTERNS.md
- All fixes must be complete, not partial workarounds

### Testing Requirements
- Every service must achieve 100% test pass rate within its scope
- No tests may be skipped or ignored to "fix" failures
- All mocking must accurately reflect actual service behavior
- Integration between services must be properly tested

### Documentation Requirements
- All patterns used must be documented for reuse
- All fixes must be explained with root cause analysis
- Progress must be tracked with concrete metrics
- Success criteria must be measurable and verified

---

**Remember**: These principles exist to ensure we deliver a production-ready enhancement that preserves all the valuable work done while meeting professional quality standards. Every decision should be evaluated against these principles.
