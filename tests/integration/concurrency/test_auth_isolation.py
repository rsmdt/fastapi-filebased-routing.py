"""Auth short-circuit isolation under concurrent load.

The most security-critical concurrency scenario: while valid requests flow
through the full pipeline, invalid requests are short-circuited with 401.
Under concurrency, an authenticated response must NEVER reach an
unauthenticated caller, and vice versa.
"""

import asyncio
import uuid
from typing import Any

import httpx
from fastapi import FastAPI

from .conftest import CONCURRENT_REQUESTS, EXPECTED_TRACES


class TestAuthShortCircuitIsolation:
    """Verify auth middleware never leaks between authenticated/unauthenticated requests."""

    async def test_mixed_auth_and_unauth_requests(self, app: FastAPI) -> None:
        """Fire authenticated and unauthenticated requests simultaneously."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            requests: list[dict[str, Any]] = []
            for i in range(CONCURRENT_REQUESTS):
                request_id = str(uuid.uuid4())
                user_id = f"user-{request_id[:8]}"
                is_authenticated = i % 2 == 0

                headers: dict[str, str] = {"X-Request-ID": request_id}
                if is_authenticated:
                    headers["Authorization"] = f"Bearer {user_id}"

                requests.append(
                    {
                        "request_id": request_id,
                        "user_id": user_id,
                        "is_authenticated": is_authenticated,
                        "headers": headers,
                    }
                )

            tasks = [
                client.get("/api/protected", headers=req["headers"])
                for req in requests
            ]
            responses = await asyncio.gather(*tasks)

        authenticated_ids: set[str] = set()
        unauthenticated_ids: set[str] = set()

        for req, response in zip(requests, responses, strict=True):
            body = response.json()

            if req["is_authenticated"]:
                # Must get 200 with correct user identity
                assert response.status_code == 200, (
                    f"Authenticated request got {response.status_code}"
                )
                assert body["request_id"] == req["request_id"]
                assert body["user_id"] == req["user_id"], (
                    f"User identity leak! Expected {req['user_id']}, "
                    f"got {body['user_id']}"
                )
                assert body["trace"] == EXPECTED_TRACES["protected"]
                authenticated_ids.add(body["request_id"])
            else:
                # Must get 401, never a 200 with someone else's data
                assert response.status_code == 401, (
                    f"Unauthenticated request got {response.status_code} "
                    f"instead of 401 — possible auth leak!"
                )
                assert body["error"] == "unauthorized"
                assert body["request_id"] == req["request_id"], (
                    f"401 response has wrong request_id: "
                    f"expected {req['request_id']}, got {body['request_id']}"
                )
                # Must NOT contain any user identity
                assert "user_id" not in body, (
                    f"401 response contains user_id={body.get('user_id')} — auth leak!"
                )
                unauthenticated_ids.add(body["request_id"])

        # Verify we got the right split
        assert len(authenticated_ids) == CONCURRENT_REQUESTS // 2
        assert len(unauthenticated_ids) == CONCURRENT_REQUESTS // 2
        # No overlap between the two sets
        assert not authenticated_ids & unauthenticated_ids

    async def test_user_identity_never_crosses_requests(self, app: FastAPI) -> None:
        """Every authenticated request carries a unique user — verify no swaps."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            users = [
                {"request_id": str(uuid.uuid4()), "user_id": f"user-{i:04d}"}
                for i in range(CONCURRENT_REQUESTS)
            ]

            tasks = [
                client.get(
                    "/api/protected",
                    headers={
                        "X-Request-ID": u["request_id"],
                        "Authorization": f"Bearer {u['user_id']}",
                    },
                )
                for u in users
            ]
            responses = await asyncio.gather(*tasks)

        seen_users: set[str] = set()

        for user, response in zip(users, responses, strict=True):
            assert response.status_code == 200
            body = response.json()

            assert body["request_id"] == user["request_id"]
            assert body["user_id"] == user["user_id"], (
                f"Identity swap! Request for {user['user_id']} "
                f"got response for {body['user_id']}"
            )
            seen_users.add(body["user_id"])

        # All user IDs are unique in responses — no duplicates from swaps
        assert len(seen_users) == CONCURRENT_REQUESTS
