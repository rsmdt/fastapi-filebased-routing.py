"""API directory middleware — appends 'api' to the middleware trace."""


async def middleware(request, call_next):  # type: ignore[no-untyped-def]
    request.state.middleware_trace.append("api")
    return await call_next(request)
