"""Protected route — returns the authenticated user's identity.

Only reachable if the auth middleware in _middleware.py allows the request through.
"""

import asyncio
import random

from fastapi import Request


async def get(request: Request):  # type: ignore[no-untyped-def]
    await asyncio.sleep(random.uniform(0.05, 1.0))
    return {
        "request_id": request.state.request_id,
        "user_id": request.state.user_id,
        "trace": request.state.middleware_trace,
        "route": "protected",
    }
