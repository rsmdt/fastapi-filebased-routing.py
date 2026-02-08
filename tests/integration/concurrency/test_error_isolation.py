"""Error handling isolation under concurrent load.

When handler A raises 404, handler B (running concurrently) must still get
its correct 200.  Error details must never leak to the wrong caller.
"""

import asyncio
import uuid
from typing import Any

import httpx
from fastapi import FastAPI

from .conftest import CONCURRENT_REQUESTS, EXPECTED_TRACES


class TestErrorIsolation:
    """Verify error responses are routed to the correct caller."""

    async def test_errors_and_successes_go_to_correct_callers(
        self, app: FastAPI
    ) -> None:
        """Mix 404-triggering and valid requests across the same route."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            requests: list[dict[str, Any]] = []
            for i in range(CONCURRENT_REQUESTS):
                request_id = str(uuid.uuid4())
                should_fail = i % 3 == 0  # ~33% fail rate
                prefix = "missing" if should_fail else "task"
                task_id = f"{prefix}-{request_id[:8]}"

                requests.append(
                    {
                        "request_id": request_id,
                        "task_id": task_id,
                        "should_fail": should_fail,
                    }
                )

            tasks = [
                client.get(
                    f"/api/tasks/{req['task_id']}",
                    headers={"X-Request-ID": req["request_id"]},
                )
                for req in requests
            ]
            responses = await asyncio.gather(*tasks)

        success_count = 0
        error_count = 0

        for req, response in zip(requests, responses, strict=True):
            if req["should_fail"]:
                assert response.status_code == 404, (
                    f"Expected 404 for {req['task_id']}, "
                    f"got {response.status_code}"
                )
                body = response.json()
                assert req["task_id"] in body["detail"], (
                    f"404 detail doesn't mention the correct task_id: {body['detail']}"
                )
                error_count += 1
            else:
                assert response.status_code == 200, (
                    f"Expected 200 for {req['task_id']}, "
                    f"got {response.status_code}"
                )
                body = response.json()
                assert body["request_id"] == req["request_id"]
                assert body["task_id"] == req["task_id"]
                assert body["trace"] == EXPECTED_TRACES["tasks"]
                success_count += 1

        # Verify we got both successes and failures
        assert error_count > 0
        assert success_count > 0
        assert error_count + success_count == CONCURRENT_REQUESTS

    async def test_error_response_never_contains_other_requests_data(
        self, app: FastAPI
    ) -> None:
        """Verify 404 responses don't accidentally include another request's payload."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            # Interleave: every other request fails
            requests: list[dict[str, Any]] = []
            for i in range(CONCURRENT_REQUESTS):
                request_id = str(uuid.uuid4())
                should_fail = i % 2 == 0

                task_id = (
                    f"missing-{request_id[:8]}" if should_fail
                    else f"task-{request_id[:8]}"
                )

                requests.append(
                    {
                        "request_id": request_id,
                        "task_id": task_id,
                        "should_fail": should_fail,
                    }
                )

            tasks = [
                client.get(
                    f"/api/tasks/{req['task_id']}",
                    headers={"X-Request-ID": req["request_id"]},
                )
                for req in requests
            ]
            responses = await asyncio.gather(*tasks)

        for req, response in zip(requests, responses, strict=True):
            body = response.json()

            if req["should_fail"]:
                assert response.status_code == 404
                # Error response must NOT contain fields from successful responses
                assert "request_id" not in body, (
                    f"Error response leaked request_id: {body}"
                )
                assert "trace" not in body, (
                    f"Error response leaked middleware trace: {body}"
                )
            else:
                assert response.status_code == 200
                assert body["request_id"] == req["request_id"]
                assert body["task_id"] == req["task_id"]
