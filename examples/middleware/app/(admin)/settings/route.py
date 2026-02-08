"""Admin settings."""
async def get() -> dict:
    """Get admin settings."""
    return {"theme": "dark", "notifications": True}

async def put(theme: str = "dark") -> dict:
    """Update admin settings."""
    return {"theme": theme, "updated": True}
