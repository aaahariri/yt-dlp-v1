#!/usr/bin/env python3
"""
Test concurrent transcription requests to find system limits.

Usage:
    python3 test_concurrency.py --concurrent 4 --model tiny
"""

import argparse
import asyncio
import time
import httpx
from typing import List


async def transcribe_request(
    client: httpx.AsyncClient,
    audio_file: str,
    model_size: str,
    request_id: int
) -> dict:
    """Send a single transcription request."""
    start = time.time()

    try:
        response = await client.post(
            "http://localhost:8000/transcribe",
            params={
                "audio_file": audio_file,
                "provider": "local",
                "model_size": model_size,
                "output_format": "json"
            },
            headers={"X-API-Key": "test-api-key-123"},
            timeout=600.0  # 10 minutes
        )
        elapsed = time.time() - start

        if response.status_code == 200:
            data = response.json()
            return {
                "request_id": request_id,
                "status": "success",
                "elapsed": elapsed,
                "segments": len(data.get("segments", [])),
                "transcription_time": data.get("transcription_time", 0)
            }
        else:
            return {
                "request_id": request_id,
                "status": "error",
                "elapsed": elapsed,
                "error": response.text
            }
    except Exception as e:
        elapsed = time.time() - start
        return {
            "request_id": request_id,
            "status": "exception",
            "elapsed": elapsed,
            "error": str(e)
        }


async def test_concurrent_requests(
    audio_file: str,
    model_size: str,
    concurrent: int
) -> List[dict]:
    """Test multiple concurrent transcription requests."""

    print(f"\\n{'='*60}")
    print(f"Testing {concurrent} concurrent requests")
    print(f"Model: {model_size}")
    print(f"Audio: {audio_file}")
    print(f"{'='*60}\\n")

    async with httpx.AsyncClient() as client:
        # Create tasks
        tasks = [
            transcribe_request(client, audio_file, model_size, i)
            for i in range(concurrent)
        ]

        # Run all concurrently
        start = time.time()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        total_elapsed = time.time() - start

    # Print results
    print(f"\\n{'='*60}")
    print(f"RESULTS - {concurrent} Concurrent Requests")
    print(f"{'='*60}\\n")

    successes = [r for r in results if isinstance(r, dict) and r["status"] == "success"]
    errors = [r for r in results if isinstance(r, dict) and r["status"] != "success"]

    print(f"Total time: {total_elapsed:.1f}s")
    print(f"Successful: {len(successes)}/{concurrent}")
    print(f"Failed: {len(errors)}/{concurrent}")

    if successes:
        avg_time = sum(r["elapsed"] for r in successes) / len(successes)
        min_time = min(r["elapsed"] for r in successes)
        max_time = max(r["elapsed"] for r in successes)

        print(f"\\nTiming (per request):")
        print(f"  Average: {avg_time:.1f}s")
        print(f"  Min: {min_time:.1f}s")
        print(f"  Max: {max_time:.1f}s")
        print(f"\\nThroughput: {concurrent / total_elapsed:.2f} requests/second")

    if errors:
        print(f"\\nErrors:")
        for err in errors[:3]:  # Show first 3 errors
            print(f"  Request {err['request_id']}: {err.get('error', 'Unknown')[:100]}")

    return results


async def main():
    parser = argparse.ArgumentParser(description="Test concurrent transcription")
    parser.add_argument(
        "--concurrent",
        type=int,
        default=4,
        help="Number of concurrent requests (default: 4)"
    )
    parser.add_argument(
        "--model",
        default="tiny",
        choices=["tiny", "small", "medium", "turbo", "large-v2"],
        help="Model size (default: tiny)"
    )
    parser.add_argument(
        "--audio",
        default="/tmp/4450a805.mp3",
        help="Path to audio file (default: /tmp/4450a805.mp3)"
    )
    parser.add_argument(
        "--test-all",
        action="store_true",
        help="Test multiple concurrency levels (1, 2, 4, 6, 8)"
    )

    args = parser.parse_args()

    # Check if audio file exists
    import os
    if not os.path.exists(args.audio):
        print(f"Error: Audio file not found: {args.audio}")
        print("\\nPlease run this first:")
        print('  curl -X POST "http://localhost:8000/extract-audio?local_file=downloads/YT-1-timeframe-can-make-you-quit-your-job.mp4" -H "X-API-Key: test-api-key-123"')
        return

    if args.test_all:
        # Test multiple concurrency levels
        levels = [1, 2, 4, 6, 8]
        all_results = {}

        for level in levels:
            results = await test_concurrent_requests(args.audio, args.model, level)
            all_results[level] = results

            # Wait between tests
            if level < levels[-1]:
                print("\\nWaiting 5 seconds before next test...\\n")
                await asyncio.sleep(5)

        # Summary
        print(f"\\n{'='*60}")
        print("SUMMARY - All Tests")
        print(f"{'='*60}\\n")
        print(f"{'Concurrent':<12} {'Success':<10} {'Avg Time':<12} {'Throughput'}")
        print("-" * 60)

        for level, results in all_results.items():
            successes = [r for r in results if isinstance(r, dict) and r["status"] == "success"]
            if successes:
                avg_time = sum(r["elapsed"] for r in successes) / len(successes)
                throughput = len(successes) / avg_time
                print(f"{level:<12} {len(successes)}/{level:<8} {avg_time:>8.1f}s    {throughput:>6.2f} req/s")

    else:
        # Single test
        await test_concurrent_requests(args.audio, args.model, args.concurrent)


if __name__ == "__main__":
    asyncio.run(main())
