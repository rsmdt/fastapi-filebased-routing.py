"""Echo route — only root directory middleware, random delay."""

import asyncio
import random

from fastapi import Request


async def get(request: Request):  # type: ignore[no-untyped-def]
    await asyncio.sleep(random.uniform(0.05, 1.0))
    return {
        "request_id": request.state.request_id,
        "trace": request.state.middleware_trace,
        "route": "echo",
    }
