"""Items route — handler-level middleware via route metaclass + random delay."""

import asyncio
import random

from fastapi import Request

from fastapi_filebased_routing.core.middleware import route


async def _handler_middleware(request, call_next):  # type: ignore[no-untyped-def]
    request.state.middleware_trace.append("items-handler")
    return await call_next(request)


class get(route):  # noqa: N801
    middleware = [_handler_middleware]

    async def handler(request: Request, item_id: str):  # type: ignore[no-untyped-def]  # noqa: N805
        await asyncio.sleep(random.uniform(0.05, 1.0))
        return {
            "request_id": request.state.request_id,
            "item_id": item_id,
            "trace": request.state.middleware_trace,
            "route": "items",
        }
