"""
Integration tests for external services.

These tests require real credentials and external service access.
They are marked with @pytest.mark.integration and skipped by default
in CI pipelines.

Usage:
    # Run all integration tests
    pytest tests/integration/ -v -s

    # Run specific test
    pytest tests/integration/test_runpod_e2e.py -v -s

Required environment variables (see .env):
    - SUPABASE_URL
    - SUPABASE_SERVICE_KEY
    - RUNPOD_ENDPOINT_ID
    - RUNPOD_API_KEY
"""
