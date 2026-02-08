"""Root middleware — stamps request ID and initializes middleware trace."""


async def middleware(request, call_next):  # type: ignore[no-untyped-def]
    request_id = request.headers.get("x-request-id", "missing")
    request.state.request_id = request_id
    request.state.middleware_trace = ["root"]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Middleware-Trace"] = ",".join(request.state.middleware_trace)
    return response
