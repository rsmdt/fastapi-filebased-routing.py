"""Users route — file-level middleware + random delay."""

import asyncio
import random

from fastapi import Request


async def _file_middleware(request, call_next):  # type: ignore[no-untyped-def]
    request.state.middleware_trace.append("users-file")
    return await call_next(request)


middleware = [_file_middleware]


async def get(request: Request):  # type: ignore[no-untyped-def]
    await asyncio.sleep(random.uniform(0.05, 1.0))
    return {
        "request_id": request.state.request_id,
        "trace": request.state.middleware_trace,
        "route": "users",
    }
