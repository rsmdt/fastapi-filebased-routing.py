"""POST request body isolation under concurrent load.

Each request carries a unique sender/content pair.  Under concurrency,
Request A's body must never appear in Request B's response.
"""

import asyncio
import uuid

import httpx
from fastapi import FastAPI

from .conftest import CONCURRENT_REQUESTS, EXPECTED_TRACES


class TestRequestBodyIsolation:
    """Verify POST request bodies never bleed across concurrent requests."""

    async def test_post_bodies_never_leak(self, app: FastAPI) -> None:
        """Fire concurrent POST requests with unique JSON bodies."""
        transport = httpx.ASGITransport(app=app)

        async with httpx.AsyncClient(
            transport=transport, base_url="http://testserver"
        ) as client:
            messages = [
                {
                    "request_id": str(uuid.uuid4()),
                    "sender": f"sender-{i:04d}",
                    "content": f"message-{uuid.uuid4()}",
                }
                for i in range(CONCURRENT_REQUESTS)
            ]

            tasks = [
                client.post(
                    "/api/messages",
                    headers={"X-Request-ID": msg["request_id"]},
                    json={"sender": msg["sender"], "content": msg["content"]},
                )
                for msg in messages
            ]
            responses = await asyncio.gather(*tasks)

        for msg, response in zip(messages, responses, strict=True):
            assert response.status_code == 201
            body = response.json()

            assert body["request_id"] == msg["request_id"]
            assert body["sender"] == msg["sender"], (
                f"Sender leak! Expected {msg['sender']}, got {body['sender']}"
            )
            assert body["content"] == msg["content"], (
                f"Content leak! Expected {msg['content']}, got {body['content']}"
            )
            assert body["trace"] == EXPECTED_TRACES["messages"]
