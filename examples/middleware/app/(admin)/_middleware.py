"""Admin middleware - verifies admin token."""
from starlette.responses import JSONResponse

async def admin_check(request, call_next):
    user = getattr(request.state, "user", None)
    if user != "admin-token":
        return JSONResponse({"error": "Admin access required"}, status_code=403)
    return await call_next(request)

middleware = [admin_check]
