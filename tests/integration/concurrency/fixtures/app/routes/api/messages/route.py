"""Messages route — accepts POST with JSON body, echoes it back.

Tests request body isolation: under concurrency, Request A's body
must never appear in Request B's response.
"""

import asyncio
import random

from fastapi import Request
from pydantic import BaseModel


class _MessageBody(BaseModel):
    sender: str
    content: str


async def _file_middleware(request, call_next):  # type: ignore[no-untyped-def]
    request.state.middleware_trace.append("messages-file")
    return await call_next(request)


middleware = [_file_middleware]


async def post(request: Request, body: _MessageBody):  # type: ignore[no-untyped-def]
    await asyncio.sleep(random.uniform(0.05, 1.0))
    return {
        "request_id": request.state.request_id,
        "sender": body.sender,
        "content": body.content,
        "trace": request.state.middleware_trace,
        "route": "messages",
    }
