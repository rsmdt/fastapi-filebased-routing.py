"""Root middleware: adds request timing to all responses."""
import time

async def middleware(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    duration = time.monotonic() - start
    response.headers["X-Response-Time"] = f"{duration:.4f}"
    return response
