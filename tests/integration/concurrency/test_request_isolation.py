"""Request isolation under concurrent load.

Fires 50 simultaneous requests across multiple routes with random 50ms–1s
delays.  Verifies request.state, path parameters, middleware traces, and
response headers are never shared between concurrent requests.
"""

import asyncio
import uuid
from typing import Any

import httpx
from fastapi import FastAPI

from .conftest import CONCURRENT_REQUESTS, EXPECTED_TRACES


class TestConcurrentRequestIsolation:
    """Verify request isolation under concurrent load with random delays."""

    async def test_no_data_leak_across_concurrent_requests(
        self, app: FastAPI
    ) -> None:
        """Fire N concurrent requests and verify every response matches its sender."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            requests: list[dict[str, Any]] = []
            for i in range(CONCURRENT_REQUESTS):
                request_id = str(uuid.uuid4())
                group = i % 3

                if group == 0:
                    url = "/echo"
                    expected_route = "echo"
                elif group == 1:
                    url = "/api/users"
                    expected_route = "users"
                else:
                    item_id = f"item-{request_id[:8]}"
                    url = f"/api/items/{item_id}"
                    expected_route = "items"

                requests.append(
                    {
                        "url": url,
                        "request_id": request_id,
                        "expected_route": expected_route,
                        "item_id": item_id if group == 2 else None,
                    }
                )

            tasks = [
                client.get(
                    req["url"],
                    headers={"X-Request-ID": req["request_id"]},
                )
                for req in requests
            ]
            responses = await asyncio.gather(*tasks)

        seen_ids: set[str] = set()

        for req, response in zip(requests, responses, strict=True):
            assert response.status_code == 200, (
                f"Route {req['url']} returned {response.status_code}"
            )

            body = response.json()

            assert body["request_id"] == req["request_id"], (
                f"Body request_id mismatch: "
                f"expected {req['request_id']}, got {body['request_id']}"
            )
            assert response.headers["x-request-id"] == req["request_id"], (
                f"Header X-Request-ID mismatch: "
                f"expected {req['request_id']}, "
                f"got {response.headers['x-request-id']}"
            )
            assert body["route"] == req["expected_route"]
            assert body["trace"] == EXPECTED_TRACES[req["expected_route"]]

            if req["item_id"] is not None:
                assert body["item_id"] == req["item_id"]

            assert response.headers["x-middleware-trace"] == ",".join(body["trace"])

            seen_ids.add(body["request_id"])

        assert len(seen_ids) == CONCURRENT_REQUESTS

    async def test_same_route_concurrent_requests_isolated(
        self, app: FastAPI
    ) -> None:
        """All requests hit the SAME route — maximizes interleaving risk."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            request_ids = [str(uuid.uuid4()) for _ in range(CONCURRENT_REQUESTS)]

            tasks = [
                client.get("/api/users", headers={"X-Request-ID": rid})
                for rid in request_ids
            ]
            responses = await asyncio.gather(*tasks)

        for rid, response in zip(request_ids, responses, strict=True):
            assert response.status_code == 200
            body = response.json()

            assert body["request_id"] == rid
            assert response.headers["x-request-id"] == rid
            assert body["route"] == "users"
            assert body["trace"] == EXPECTED_TRACES["users"]

    async def test_path_parameter_isolation_under_concurrency(
        self, app: FastAPI
    ) -> None:
        """Different item_ids must never bleed across responses."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            items = [
                {"item_id": f"item-{i:04d}", "request_id": str(uuid.uuid4())}
                for i in range(CONCURRENT_REQUESTS)
            ]

            tasks = [
                client.get(
                    f"/api/items/{item['item_id']}",
                    headers={"X-Request-ID": item["request_id"]},
                )
                for item in items
            ]
            responses = await asyncio.gather(*tasks)

        for item, response in zip(items, responses, strict=True):
            assert response.status_code == 200
            body = response.json()

            assert body["request_id"] == item["request_id"]
            assert body["item_id"] == item["item_id"]
            assert body["trace"] == EXPECTED_TRACES["items"]

    async def test_middleware_state_not_shared_between_requests(
        self, app: FastAPI
    ) -> None:
        """Verify request.state.middleware_trace is never polluted by other requests.

        If traces leaked, we'd see traces like ["root", "api", "users-file", "root"]
        or traces from a different route (e.g., "items-handler" on a /users response).
        """
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            routes = [
                ("/echo", "echo"),
                ("/api/users", "users"),
                ("/api/items/test-item", "items"),
            ]

            tasks = []
            expected = []
            for i in range(CONCURRENT_REQUESTS):
                url, route_name = routes[i % len(routes)]
                rid = str(uuid.uuid4())
                tasks.append(client.get(url, headers={"X-Request-ID": rid}))
                expected.append(route_name)

            responses = await asyncio.gather(*tasks)

        for route_name, response in zip(expected, responses, strict=True):
            body = response.json()
            trace = body["trace"]

            assert trace == EXPECTED_TRACES[route_name], (
                f"Trace pollution detected on {route_name}! "
                f"Expected {EXPECTED_TRACES[route_name]}, got {trace}"
            )

            valid_entries = set(EXPECTED_TRACES[route_name])
            for entry in trace:
                assert entry in valid_entries, (
                    f"Foreign trace entry '{entry}' found in {route_name} response"
                )
