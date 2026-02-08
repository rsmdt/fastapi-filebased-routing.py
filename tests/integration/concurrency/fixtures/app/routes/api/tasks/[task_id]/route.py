"""Tasks route — raises HTTPException for specific task IDs.

Tests error handling under concurrency: when handler A raises 404,
handler B (running concurrently) must still get its correct 200 response.
Task IDs starting with "missing-" trigger a 404 Not Found.
"""

import asyncio
import random

from fastapi import HTTPException, Request


async def get(request: Request, task_id: str):  # type: ignore[no-untyped-def]
    await asyncio.sleep(random.uniform(0.05, 1.0))

    if task_id.startswith("missing-"):
        raise HTTPException(
            status_code=404,
            detail=f"Task {task_id} not found",
        )

    return {
        "request_id": request.state.request_id,
        "task_id": task_id,
        "trace": request.state.middleware_trace,
        "route": "tasks",
    }
