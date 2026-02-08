"""Health check endpoint."""


def get() -> dict:
    """Check service health."""
    return {
        "status": "healthy",
        "service": "fastapi-filebased-routing-basic-example",
    }
