"""Users route with file-level middleware."""

async def log_access(request, call_next):
    print(f"Accessing users endpoint: {request.method}")
    return await call_next(request)

middleware = [log_access]

async def get(limit: int = 10) -> dict:
    """List users."""
    return {"users": [], "limit": limit}

async def post(name: str) -> dict:
    """Create user."""
    return {"name": name, "created": True}
