"""Auth middleware — short-circuits with 401 for missing/invalid tokens.

This is the security-critical middleware: under concurrency, an authenticated
response must NEVER leak to an unauthenticated caller, and vice versa.
"""

from starlette.responses import JSONResponse


async def middleware(request, call_next):  # type: ignore[no-untyped-def]
    token = request.headers.get("authorization", "")
    if not token.startswith("Bearer "):
        return JSONResponse(
            {"error": "unauthorized", "request_id": request.state.request_id},
            status_code=401,
        )
    request.state.user_id = token.removeprefix("Bearer ")
    request.state.middleware_trace.append("auth")
    return await call_next(request)
