"""Health check - no middleware."""
async def get() -> dict:
    return {"status": "ok"}
