# 📈 Service Mocking Patterns - Proven Templates

**Purpose**: Reusable solutions for common service mocking challenges in async Python testing

## 🏆 Proven Patterns (Ready for Immediate Use)

### 🔧 Redis AsyncMock Pattern ✅ PROVEN
**Status**: ✅ Successfully applied to JobManager (18/18 tests passing)
**Use Case**: Services using Redis/async database operations
**Next Application**: Usage Tracker (Est: 30 min to apply)

#### Problem Solved
- **Error**: `TypeError: object MagicMock can't be used in 'await' expression`
- **Root Cause**: Redis client methods need AsyncMock for async operations

#### Template Code
```python
@pytest.fixture
def mock_redis_client():
    """Mock Redis client with all async methods."""
    mock_client = MagicMock()

    # Connection management
    mock_client.ping = AsyncMock(return_value=True)
    mock_client.close = AsyncMock(return_value=None)
    mock_client.aclose = AsyncMock(return_value=None)  # Legacy compatibility

    # Basic operations
    mock_client.set = AsyncMock(return_value=True)
    mock_client.get = AsyncMock(return_value=None)
    mock_client.delete = AsyncMock(return_value=1)
    mock_client.expire = AsyncMock(return_value=1)

    # Sorted set operations
    mock_client.zadd = AsyncMock(return_value=1)
    mock_client.zrange = AsyncMock(return_value=[])
    mock_client.zrevrange = AsyncMock(return_value=[])
    mock_client.zrangebyscore = AsyncMock(return_value=[])
    mock_client.zrem = AsyncMock(return_value=1)
    mock_client.zcard = AsyncMock(return_value=0)

    return mock_client

@pytest.fixture
def mock_redis_connection_pool():
    """Mock Redis connection pool."""
    mock_pool = MagicMock()
    mock_pool.disconnect = AsyncMock(return_value=None)
    return mock_pool
```

#### Application Steps
1. **Identify Redis operations** in the service's implementation
2. **Add missing async methods** to the fixture if needed
3. **Update connection pool mocking** for cleanup operations
4. **Fix test expectations** to match actual implementation APIs
5. **Verify all Redis calls** are properly mocked with AsyncMock

#### Services That Need This Pattern
- ✅ **JobManager**: Applied successfully (18/18 tests)
- 🎯 **Usage Tracker**: Ready to apply (10 failed tests with same error)
- 🔄 **Health Router**: May need for some Redis connectivity tests

---

### 🔌 API Compatibility Pattern ✅ PROVEN
**Status**: ✅ Successfully applied to Gemini Service (73/75 tests passing)
**Use Case**: Third-party API client compatibility issues
**Achievement**: Fixed Google Gemini API v0.3.2 compatibility

#### Problem Solved
- **Error**: `module 'google.generativeai' has no attribute 'Client'`
- **Root Cause**: API breaking changes in google-generativeai library

#### Solution Approach
1. **Identify API changes** by checking library documentation/source
2. **Update client initialization** patterns to match new API
3. **Fix method call patterns** (file upload, deletion, content generation)
4. **Add compatibility attributes** for test framework expectations
5. **Update test expectations** to match actual API behavior

#### Key Fixes Applied
```python
# OLD (v0.2.x):
self._file_client = genai.Client()

# NEW (v0.3.2):
self._file_client = genai  # Use module directly

# OLD file upload:
files.upload(file_data, mime_type=mime_type)

# NEW file upload:
genai.upload_file(file_data, mime_type=mime_type, display_name=filename)
```

---

### 📋 NPO Model Pattern ✅ PROVEN
**Status**: ✅ Successfully verified (48/48 response adapter tests passing)
**Use Case**: Pydantic model validation and NPO format transformations
**Achievement**: Confirmed NPO functionality completely intact

#### Verification Results
- **Response Adapter Tests**: 48/48 passing (100% success rate)
- **Model Coverage**: 96% (models/extraction.py)
- **NPO Transformations**: All 24 transformation patterns working
- **Model Imports**: No ValidationErrors detected

#### Pattern Recognition
- **Issue was NOT model structure** - models work correctly
- **Issue was service connectivity** - mocking problems elsewhere
- **NPO enhancements are robust** - no regressions from enhancements

## 🔍 Identified Patterns (Ready to Implement)

### 🌐 HTTP AsyncMock Pattern (LLM Service)
**Status**: 🔍 Pattern identified, ready to implement
**Use Case**: Services using aiohttp HTTP clients
**Target**: LLM Service (12 failed tests)

#### Problem Analysis
- **Error**: `'coroutine' object does not support the asynchronous context manager protocol`
- **Location**: `async with aiohttp.ClientSession(...)` in LLM service
- **Root Cause**: aiohttp.ClientSession needs proper AsyncMock context manager support

#### Proposed Solution Template
```python
@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp ClientSession with async context manager support."""
    mock_session = AsyncMock()

    # Context manager support
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)

    # HTTP methods
    mock_response = AsyncMock()
    mock_response.status = 200
    mock_response.json = AsyncMock(return_value={"result": "test"})
    mock_response.text = AsyncMock(return_value="test response")

    mock_session.post = AsyncMock(return_value=mock_response)
    mock_session.get = AsyncMock(return_value=mock_response)

    return mock_session
```

#### Estimated Implementation
- **Time**: 30 minutes
- **Files**: `tests/unit/test_llm_service.py`
- **Expected Result**: 43/43 tests passing (currently 31/43)

---

### 📄 FastAPI Response Pattern (Web Router)
**Status**: 🔍 Pattern identified, ready to implement
**Use Case**: FastAPI endpoint testing with template responses
**Target**: Web Router (15 failed tests)

#### Problem Analysis
- **Error**: `AttributeError: 'dict' object has no attribute 'encode'`
- **Location**: Starlette response handling in FastAPI test client
- **Root Cause**: Template response mocking returning dict instead of proper response object

#### Proposed Solution Approach
1. **Mock template responses** to return proper Starlette Response objects
2. **Fix response encoding** by ensuring bytes/string handling
3. **Update test client expectations** for HTML template rendering
4. **Mock template context** properly for Jinja2 rendering

#### Estimated Implementation
- **Time**: 20 minutes
- **Files**: `tests/unit/test_web_router.py`
- **Expected Result**: 26/26 tests passing (currently 11/26)

---

### 💉 Dependency Injection Pattern (Extraction Router)
**Status**: 🔍 Pattern identified, ready to implement
**Use Case**: FastAPI dependency injection mocking
**Target**: Extraction Router (18 failed tests)

#### Problem Analysis
- **Error**: Various dependency injection failures with `get_job_manager()` and other services
- **Root Cause**: FastAPI dependency overrides not properly configured in tests

#### Proposed Solution Approach
1. **Mock dependency providers** (`get_job_manager`, `get_usage_tracker`, etc.)
2. **Configure FastAPI dependency overrides** in test setup
3. **Ensure service method mocking** aligns with actual implementations
4. **Fix async service call patterns** in router tests

#### Estimated Implementation
- **Time**: 25 minutes
- **Files**: `tests/unit/test_extraction_router.py`
- **Expected Result**: 18/18 tests passing (currently 0/18)

## 🎯 Pattern Application Priority

### HIGH PRIORITY (Maximum Test Impact)
1. **🔧 Usage Tracker Redis Pattern** (30 min) → +10 tests passing
2. **🌐 LLM Service HTTP Pattern** (30 min) → +12 tests passing

### MEDIUM PRIORITY (Cleanup Remaining)
3. **📄 Web Router Response Pattern** (20 min) → +15 tests passing
4. **💉 Extraction Router Dependencies** (25 min) → +18 tests passing

**📊 TOTAL PROJECTED IMPACT**: 73 → 18 failing tests (96% pass rate)

## 🔄 Pattern Development Workflow

### For New Patterns
1. **Identify error signatures** and root causes
2. **Research the service/library** for proper async patterns
3. **Create minimal test case** to reproduce the issue
4. **Develop template solution** with proper AsyncMock usage
5. **Apply and verify** the pattern works
6. **Document in this file** for future reuse
7. **Update DASHBOARD.md** with new pattern availability

### For Existing Patterns
1. **Copy template from this file**
2. **Adapt service-specific details** (method names, return values)
3. **Apply systematically** to all failing tests in the service
4. **Verify 100% pass rate** for the service
5. **Update DASHBOARD.md** with completion status

---

**🎯 Goal**: Build a comprehensive library of reusable patterns that make future async service testing systematic and predictable.
