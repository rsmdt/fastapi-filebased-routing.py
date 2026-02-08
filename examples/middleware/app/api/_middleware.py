"""Auth middleware for all /api/ routes."""
from starlette.responses import JSONResponse

async def auth_check(request, call_next):
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    request.state.user = token.removeprefix("Bearer ")
    return await call_next(request)

middleware = [auth_check]
