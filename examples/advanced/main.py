"""Advanced routing example showcasing all file-based routing patterns.

This example demonstrates:
- Optional parameters with [[param]]
- Catch-all parameters with [...param]
- Route groups with (name)
- WebSocket support
- Server-Sent Events (SSE) with StreamingResponse
- Mixed sync and async handlers
"""

from fastapi import FastAPI
from fastapi_filebased_routing import create_router_from_path

app = FastAPI(
    title="Advanced Routing Demo",
    description="Demonstrates all fastapi-filebased-routing patterns",
)

# Create router from the app directory
router = create_router_from_path("app")

# Include the router in the FastAPI app
app.include_router(router)


@app.on_event("startup")
async def print_routes():
    """Print all discovered routes for educational purposes."""
    print("\n" + "=" * 80)
    print("DISCOVERED ROUTES")
    print("=" * 80)

    # Group routes by their paths
    routes_info = []
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            # HTTP routes
            methods = sorted(route.methods) if route.methods else []
            if methods:
                routes_info.append((route.path, ", ".join(methods), "HTTP"))
        elif hasattr(route, "path"):
            # WebSocket routes
            routes_info.append((route.path, "WEBSOCKET", "WS"))

    # Sort by path for readability
    routes_info.sort()

    for path, methods, route_type in routes_info:
        print(f"  [{route_type:^4}] {methods:20} {path}")

    print("=" * 80 + "\n")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
