# Testing Guide

## Quick Start

### Run All Tests
```bash
source .venv/bin/activate
pytest tests/unit/ tests/test_routers.py -v
```

### Run with Coverage
```bash
pytest tests/unit/ tests/test_routers.py --cov=app --cov-report=term-missing --cov-report=html
open htmlcov/index.html  # View HTML coverage report
```

## Test Organization

```
tests/
├── conftest.py                 # Shared fixtures and configuration
├── unit/
│   └── test_utils.py          # 38 unit tests for utility functions
└── test_routers.py            # 41 integration tests for API routers
```

## Running Specific Tests

### By Test File
```bash
pytest tests/unit/test_utils.py -v
pytest tests/test_routers.py -v
```

### By Test Class
```bash
pytest tests/test_routers.py::TestDownloadRouter -v
pytest tests/unit/test_utils.py::TestFilenameUtils -v
```

### By Test Function
```bash
pytest tests/unit/test_utils.py::TestFilenameUtils::test_sanitize_filename_basic -v
pytest tests/test_routers.py::TestAuthentication::test_missing_api_key -v
```

### By Marker (if using markers)
```bash
pytest -m unit          # Run only unit tests
pytest -m integration   # Run only integration tests
pytest -m "not slow"    # Skip slow tests
```

## Test Output Options

### Minimal Output
```bash
pytest tests/unit/ tests/test_routers.py -q
```

### Verbose Output
```bash
pytest tests/unit/ tests/test_routers.py -v
```

### Very Verbose (shows test parameters)
```bash
pytest tests/unit/ tests/test_routers.py -vv
```

### Show Print Statements
```bash
pytest tests/unit/ tests/test_routers.py -v -s
```

## Debugging Failed Tests

### Show Full Traceback
```bash
pytest tests/unit/ tests/test_routers.py -v --tb=long
```

### Stop at First Failure
```bash
pytest tests/unit/ tests/test_routers.py -x
```

### Drop into Debugger on Failure
```bash
pytest tests/unit/ tests/test_routers.py --pdb
```

### Run Last Failed Tests Only
```bash
pytest --lf
```

## Coverage Options

### Terminal Report with Missing Lines
```bash
pytest tests/unit/ tests/test_routers.py --cov=app --cov-report=term-missing
```

### HTML Report
```bash
pytest tests/unit/ tests/test_routers.py --cov=app --cov-report=html
open htmlcov/index.html
```

### Coverage for Specific Module
```bash
pytest tests/unit/test_utils.py --cov=app.utils --cov-report=term-missing
```

## Test Structure

### Unit Tests (tests/unit/test_utils.py)

**38 tests** covering:
- `app/utils/filename_utils.py` (19 tests)
- `app/utils/timestamp_utils.py` (8 tests)
- `app/utils/platform_utils.py` (11 tests)

**Example:**
```python
def test_sanitize_filename_basic():
    """Test basic filename sanitization."""
    assert sanitize_filename("hello world") == "hello world"
    assert sanitize_filename("test/file") == "test-file"
```

### Integration Tests (tests/test_routers.py)

**41 tests** covering:
- Authentication (3 tests)
- Download router (4 tests)
- Subtitles router (5 tests)
- Audio router (3 tests)
- Transcription router (6 tests)
- Playlist router (3 tests)
- Screenshot router (3 tests)
- Cache router (6 tests)
- Admin router (7 tests)
- Health check (1 test)

**Example:**
```python
@pytest.mark.asyncio
async def test_missing_api_key(client):
    """Test requests without API key are rejected."""
    response = await client.get("/cache")
    assert response.status_code == 401
```

## Fixtures Available

### Client Fixtures
- `client` - Async HTTP client for testing FastAPI endpoints
- `api_headers` - Headers with valid API key
- `api_key` - Test API key string

### Mock Data Fixtures
- `mock_ytdlp_info` - Mock video metadata
- `mock_ytdlp_playlist_info` - Mock playlist metadata
- `youtube_url` - Sample YouTube URL
- `tiktok_url` - Sample TikTok URL
- `instagram_url` - Sample Instagram URL

### Environment Fixtures
- `mock_env_vars` - Mocked environment variables for testing

## Writing New Tests

### Unit Test Template
```python
def test_my_function():
    """Test description."""
    # Arrange
    input_data = "test"

    # Act
    result = my_function(input_data)

    # Assert
    assert result == expected_output
```

### Async Integration Test Template
```python
@pytest.mark.asyncio
async def test_my_endpoint(client, api_headers):
    """Test endpoint description."""
    # Arrange
    request_data = {"key": "value"}

    # Act
    response = await client.post("/endpoint", headers=api_headers, json=request_data)

    # Assert
    assert response.status_code == 200
    data = response.json()
    assert "expected_key" in data
```

## Common Test Patterns

### Testing Authentication
```python
@pytest.mark.asyncio
async def test_endpoint_requires_auth(client):
    response = await client.get("/protected-endpoint")
    assert response.status_code == 401
```

### Testing Input Validation
```python
@pytest.mark.asyncio
async def test_endpoint_validates_input(client, api_headers):
    response = await client.post("/endpoint", headers=api_headers, json={})
    assert response.status_code == 422  # Validation error
```

### Mocking External Services
```python
@pytest.mark.asyncio
async def test_with_mocked_service(client, api_headers):
    with patch("app.services.my_service.external_call") as mock:
        mock.return_value = {"data": "mocked"}
        response = await client.get("/endpoint", headers=api_headers)
        assert response.status_code == 200
```

## Continuous Integration

### GitHub Actions Example
```yaml
- name: Run Tests
  run: |
    source .venv/bin/activate
    pytest tests/unit/ tests/test_routers.py --cov=app --cov-report=xml

- name: Upload Coverage
  uses: codecov/codecov-action@v3
  with:
    file: ./coverage.xml
```

## Troubleshooting

### Tests Not Found
Make sure you're in the project root and specify the correct paths:
```bash
pytest tests/unit/ tests/test_routers.py
```

### Import Errors
Activate virtual environment:
```bash
source .venv/bin/activate
```

### Async Warnings
Tests using async fixtures should be marked with `@pytest.mark.asyncio`:
```python
@pytest.mark.asyncio
async def test_async_endpoint(client):
    ...
```

### Mock Not Applied
Make sure to patch where the function is imported, not where it's defined:
```python
# ❌ Wrong
with patch("scripts.module.function"):

# ✅ Correct (patch where imported)
with patch("app.routers.router.function"):
```

## Test Metrics

Current test suite metrics:
- **Total Tests**: 79
- **Unit Tests**: 38
- **Integration Tests**: 41
- **Pass Rate**: 100%
- **Code Coverage**: 46%
- **Utility Coverage**: 99%

## Resources

- [pytest Documentation](https://docs.pytest.org/)
- [pytest-asyncio Documentation](https://pytest-asyncio.readthedocs.io/)
- [FastAPI Testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [httpx Testing](https://www.python-httpx.org/advanced/)

---

*Last Updated: December 15, 2025*
