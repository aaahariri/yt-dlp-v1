"""
RunPod End-to-End Integration Test

This test validates the complete transcription cycle:
1. Search YouTube for a video using a specific term
2. Create a document in Supabase (triggers Edge Function flow)
3. Send job to RunPod endpoint
4. Poll for completion (check Supabase document status)
5. Verify transcription was saved correctly
6. Cleanup: Delete test document and transcription

IMPORTANT: This test uses REAL services and should be run manually.
It requires the following environment variables:
- SUPABASE_URL
- SUPABASE_SERVICE_KEY
- RUNPOD_ENDPOINT_ID
- RUNPOD_API_KEY

Usage:
    pytest tests/integration/test_runpod_e2e.py -v -s

    # Or run specific test:
    pytest tests/integration/test_runpod_e2e.py::TestRunPodE2E::test_full_transcription_cycle -v -s
"""

import os
import time
import uuid
import pytest
import requests
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from dataclasses import dataclass


# =============================================================================
# Configuration
# =============================================================================

@dataclass
class TestConfig:
    """Test configuration loaded from environment variables."""
    supabase_url: str
    supabase_key: str
    runpod_endpoint_id: str
    runpod_api_key: str

    # Test parameters
    youtube_search_term: str = "Stock Technical Analysis short"
    max_video_duration: int = 120  # Max duration in seconds to keep test fast
    status_poll_interval: int = 10  # Seconds between status checks
    max_wait_time: int = 300  # Max seconds to wait for job completion

    @classmethod
    def from_env(cls) -> "TestConfig":
        """Load configuration from environment variables."""
        required_vars = [
            "SUPABASE_URL",
            "SUPABASE_SERVICE_KEY",
            "RUNPOD_ENDPOINT_ID",
            "RUNPOD_API_KEY"
        ]

        missing = [v for v in required_vars if not os.environ.get(v)]
        if missing:
            raise pytest.skip(f"Missing required environment variables: {missing}")

        return cls(
            supabase_url=os.environ["SUPABASE_URL"],
            supabase_key=os.environ["SUPABASE_SERVICE_KEY"],
            runpod_endpoint_id=os.environ["RUNPOD_ENDPOINT_ID"],
            runpod_api_key=os.environ["RUNPOD_API_KEY"]
        )

    @property
    def runpod_run_url(self) -> str:
        return f"https://api.runpod.ai/v2/{self.runpod_endpoint_id}/run"

    @property
    def runpod_status_url(self) -> str:
        return f"https://api.runpod.ai/v2/{self.runpod_endpoint_id}/status"


# =============================================================================
# Supabase Client Helper
# =============================================================================

class SupabaseTestClient:
    """Simple Supabase client for test operations."""

    def __init__(self, config: TestConfig):
        self.config = config
        self.base_url = config.supabase_url
        self.headers = {
            "apikey": config.supabase_key,
            "Authorization": f"Bearer {config.supabase_key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make authenticated request to Supabase REST API."""
        url = f"{self.base_url}/rest/v1/{endpoint}"
        return requests.request(method, url, headers=self.headers, **kwargs)

    def insert_document(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Insert a new document and return the created record."""
        response = self._request("POST", "documents", json=data)
        response.raise_for_status()
        return response.json()[0]

    def get_document(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get a document by ID."""
        response = self._request(
            "GET",
            f"documents?id=eq.{document_id}&select=*"
        )
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None

    def delete_document(self, document_id: str) -> bool:
        """Delete a document by ID."""
        response = self._request("DELETE", f"documents?id=eq.{document_id}")
        return response.status_code in [200, 204]

    def get_transcription(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Get transcription for a document."""
        response = self._request(
            "GET",
            f"document_transcriptions?document_id=eq.{document_id}&select=*"
        )
        response.raise_for_status()
        data = response.json()
        return data[0] if data else None

    def delete_transcription(self, document_id: str) -> bool:
        """Delete transcription for a document."""
        response = self._request(
            "DELETE",
            f"document_transcriptions?document_id=eq.{document_id}"
        )
        return response.status_code in [200, 204]

    def check_transcription_has_segments(self, document_id: str) -> bool:
        """Check if transcription exists and has segments."""
        trans = self.get_transcription(document_id)
        if not trans:
            return False
        segments = trans.get("segments", [])
        return len(segments) > 0


# =============================================================================
# YouTube Search Helper
# =============================================================================

def search_youtube_video(search_term: str, max_duration: int = 120) -> Optional[Dict[str, Any]]:
    """
    Search for a YouTube video using yt-dlp.
    Returns video info dict or None if no suitable video found.

    Args:
        search_term: Search query
        max_duration: Maximum video duration in seconds

    Returns:
        Dict with keys: url, video_id, title, duration
    """
    import yt_dlp

    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'default_search': 'ytsearch5',  # Get 5 results
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        try:
            result = ydl.extract_info(f"ytsearch5:{search_term}", download=False)
            entries = result.get('entries', [])

            # Find first video within duration limit
            for entry in entries:
                duration = entry.get('duration', 0)
                if duration and duration <= max_duration:
                    return {
                        'url': entry.get('webpage_url'),
                        'video_id': entry.get('id'),
                        'title': entry.get('title'),
                        'duration': duration
                    }

            # If no short video found, return first result anyway with warning
            if entries:
                entry = entries[0]
                print(f"WARNING: No video under {max_duration}s found, using first result")
                return {
                    'url': entry.get('webpage_url'),
                    'video_id': entry.get('id'),
                    'title': entry.get('title'),
                    'duration': entry.get('duration', 0)
                }

        except Exception as e:
            print(f"YouTube search failed: {e}")

    return None


# =============================================================================
# RunPod API Helper
# =============================================================================

class RunPodClient:
    """Simple RunPod API client for test operations."""

    def __init__(self, config: TestConfig):
        self.config = config

    def submit_job(self, document_id: str) -> Dict[str, Any]:
        """Submit a job to RunPod and return the response."""
        payload = {
            "input": {
                "queue": "video_audio_transcription",
                "vt_seconds": 1800,
                "jobs": [
                    {
                        "msg_id": 1,
                        "read_ct": 1,
                        "enqueued_at": datetime.now(timezone.utc).isoformat(),
                        "document_id": document_id,
                        "message": {"document_id": document_id}
                    }
                ]
            }
        }

        response = requests.post(
            self.config.runpod_run_url,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.runpod_api_key}"
            },
            json=payload
        )
        response.raise_for_status()
        return response.json()

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a RunPod job."""
        response = requests.get(
            f"{self.config.runpod_status_url}/{job_id}",
            headers={
                "Authorization": f"Bearer {self.config.runpod_api_key}"
            }
        )
        response.raise_for_status()
        return response.json()


# =============================================================================
# Test Class
# =============================================================================

@pytest.mark.integration
class TestRunPodE2E:
    """End-to-end integration tests for RunPod transcription pipeline."""

    @pytest.fixture
    def config(self) -> TestConfig:
        """Load test configuration from environment."""
        return TestConfig.from_env()

    @pytest.fixture
    def supabase(self, config: TestConfig) -> SupabaseTestClient:
        """Create Supabase test client."""
        return SupabaseTestClient(config)

    @pytest.fixture
    def runpod(self, config: TestConfig) -> RunPodClient:
        """Create RunPod test client."""
        return RunPodClient(config)

    def test_full_transcription_cycle(
        self,
        config: TestConfig,
        supabase: SupabaseTestClient,
        runpod: RunPodClient
    ):
        """
        Test the complete transcription cycle:
        1. Search for a YouTube video
        2. Create document in Supabase
        3. Submit job to RunPod
        4. Wait for completion
        5. Verify transcription
        6. Cleanup
        """
        document_id = None

        try:
            # =================================================================
            # Step 1: Search for a YouTube video
            # =================================================================
            print(f"\n{'='*60}")
            print("STEP 1: Searching for YouTube video...")
            print(f"{'='*60}")

            video = search_youtube_video(
                config.youtube_search_term,
                config.max_video_duration
            )

            assert video is not None, "Failed to find a suitable YouTube video"
            print(f"Found: {video['title'][:50]}...")
            print(f"URL: {video['url']}")
            print(f"Duration: {video['duration']}s")

            # =================================================================
            # Step 2: Create document in Supabase
            # =================================================================
            print(f"\n{'='*60}")
            print("STEP 2: Creating document in Supabase...")
            print(f"{'='*60}")

            document_id = str(uuid.uuid4())

            doc_data = {
                "id": document_id,
                "video_id": video['video_id'],
                "url": video['url'],
                "canonical_url": video['url'],
                "title": video['title'],
                "duration": video['duration'],
                "platform": "youtube",
                "media_format": "video",
                "processing_status": "pending",
                "metadata": {
                    "test": True,
                    "search_term": config.youtube_search_term,
                    "created_by": "integration_test"
                }
            }

            created_doc = supabase.insert_document(doc_data)
            print(f"Created document: {document_id}")
            print(f"Status: {created_doc.get('processing_status')}")

            # Verify document was created with pending status
            assert created_doc['processing_status'] == 'pending'

            # =================================================================
            # Step 3: Submit job to RunPod
            # =================================================================
            print(f"\n{'='*60}")
            print("STEP 3: Submitting job to RunPod...")
            print(f"{'='*60}")

            job_response = runpod.submit_job(document_id)
            runpod_job_id = job_response.get('id')

            print(f"RunPod Job ID: {runpod_job_id}")
            print(f"Status: {job_response.get('status')}")

            assert runpod_job_id is not None, "Failed to get RunPod job ID"
            assert job_response.get('status') == 'IN_QUEUE', f"Unexpected status: {job_response.get('status')}"

            # =================================================================
            # Step 4: Wait for completion
            # =================================================================
            print(f"\n{'='*60}")
            print("STEP 4: Waiting for job completion...")
            print(f"{'='*60}")

            start_time = time.time()
            last_status = None

            while time.time() - start_time < config.max_wait_time:
                # Check RunPod job status
                try:
                    runpod_status = runpod.get_job_status(runpod_job_id)
                    status = runpod_status.get('status')

                    if status != last_status:
                        print(f"RunPod status: {status}")
                        last_status = status

                    if status == 'COMPLETED':
                        print("RunPod job completed!")
                        break
                    elif status == 'FAILED':
                        error = runpod_status.get('error', 'Unknown error')
                        pytest.fail(f"RunPod job failed: {error}")
                    elif status == 'CANCELLED':
                        pytest.fail("RunPod job was cancelled")
                    elif status == 'TIMED_OUT':
                        pytest.fail("RunPod job timed out")

                except Exception as e:
                    print(f"Error checking RunPod status: {e}")

                # Also check Supabase document status
                doc = supabase.get_document(document_id)
                if doc:
                    db_status = doc.get('processing_status')
                    if db_status == 'completed':
                        print(f"Document status: {db_status}")
                        break
                    elif db_status == 'error':
                        error = doc.get('processing_error', 'Unknown error')
                        pytest.fail(f"Document processing failed: {error}")

                time.sleep(config.status_poll_interval)
                elapsed = int(time.time() - start_time)
                print(f"Waiting... ({elapsed}s / {config.max_wait_time}s)")

            else:
                pytest.fail(f"Timeout waiting for job completion after {config.max_wait_time}s")

            # =================================================================
            # Step 5: Verify transcription
            # =================================================================
            print(f"\n{'='*60}")
            print("STEP 5: Verifying transcription...")
            print(f"{'='*60}")

            # Check document status
            final_doc = supabase.get_document(document_id)
            assert final_doc is not None, "Document not found after processing"
            assert final_doc['processing_status'] == 'completed', \
                f"Unexpected status: {final_doc['processing_status']}"
            print(f"Document status: {final_doc['processing_status']}")

            # Check transcription
            transcription = supabase.get_transcription(document_id)
            assert transcription is not None, "Transcription not found"

            segments = transcription.get('segments', [])
            assert len(segments) > 0, "Transcription has no segments"

            print(f"Transcription found:")
            print(f"  - Language: {transcription.get('language')}")
            print(f"  - Source: {transcription.get('source')}")
            print(f"  - Segments: {len(segments)}")

            # Check metadata
            metadata = transcription.get('metadata', {})
            print(f"  - Model: {metadata.get('model')}")
            print(f"  - Provider: {metadata.get('provider')}")
            print(f"  - Word count: {metadata.get('word_count')}")

            # Show first segment as sample
            if segments:
                first_seg = segments[0]
                print(f"  - First segment: [{first_seg.get('start'):.1f}s] {first_seg.get('text', '')[:50]}...")

            print(f"\n{'='*60}")
            print("TEST PASSED!")
            print(f"{'='*60}")

        finally:
            # =================================================================
            # Step 6: Cleanup
            # =================================================================
            if document_id:
                print(f"\n{'='*60}")
                print("CLEANUP: Deleting test data...")
                print(f"{'='*60}")

                # Delete transcription first (foreign key constraint)
                if supabase.delete_transcription(document_id):
                    print(f"Deleted transcription for document {document_id}")
                else:
                    print(f"No transcription to delete for {document_id}")

                # Delete document
                if supabase.delete_document(document_id):
                    print(f"Deleted document {document_id}")
                else:
                    print(f"Failed to delete document {document_id}")

    def test_existing_transcription_not_overwritten(
        self,
        config: TestConfig,
        supabase: SupabaseTestClient,
        runpod: RunPodClient
    ):
        """
        Test that running a job for a document with existing transcription
        doesn't process (document already not pending).
        """
        document_id = None

        try:
            # Create a document that's already completed
            document_id = str(uuid.uuid4())

            doc_data = {
                "id": document_id,
                "video_id": "test_existing",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "canonical_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title": "Test - Already Completed",
                "duration": 60,
                "platform": "youtube",
                "media_format": "video",
                "processing_status": "completed",  # Already completed!
                "processed_at": datetime.now(timezone.utc).isoformat(),
                "metadata": {"test": True}
            }

            supabase.insert_document(doc_data)
            print(f"Created already-completed document: {document_id}")

            # Submit job - should return quickly since doc is not pending
            job_response = runpod.submit_job(document_id)
            runpod_job_id = job_response.get('id')
            print(f"Submitted job: {runpod_job_id}")

            # Wait for RunPod to process (should be fast since it skips)
            time.sleep(30)

            runpod_status = runpod.get_job_status(runpod_job_id)
            print(f"RunPod status: {runpod_status.get('status')}")

            # Check the job result - should show "deleted" (not pending)
            if runpod_status.get('status') == 'COMPLETED':
                output = runpod_status.get('output', {})
                results = output.get('results', [])
                if results:
                    assert results[0].get('status') == 'deleted', \
                        "Job should be skipped for already-completed documents"
                    print("Confirmed: Job correctly skipped (document not pending)")

        finally:
            if document_id:
                supabase.delete_transcription(document_id)
                supabase.delete_document(document_id)


# =============================================================================
# Standalone Runner
# =============================================================================

if __name__ == "__main__":
    """
    Run tests directly without pytest for quick manual testing.

    Usage:
        python tests/integration/test_runpod_e2e.py
    """
    from dotenv import load_dotenv
    load_dotenv()

    print("="*60)
    print("RunPod E2E Integration Test - Manual Runner")
    print("="*60)

    try:
        config = TestConfig.from_env()
        supabase = SupabaseTestClient(config)
        runpod_client = RunPodClient(config)

        test = TestRunPodE2E()
        test.test_full_transcription_cycle(config, supabase, runpod_client)

    except Exception as e:
        print(f"\nTEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        exit(1)
