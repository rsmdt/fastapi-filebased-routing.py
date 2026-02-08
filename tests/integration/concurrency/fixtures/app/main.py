"""Concurrency test app — a realistic FastAPI app with file-based routing.

Can be run standalone for manual testing:
    uvicorn tests.integration.fixtures.concurrency_app.main:app --reload

Routes exercise all three middleware layers with random delays (50ms–1s)
to surface data leaks and request isolation issues under concurrent load.
"""

from pathlib import Path

from fastapi import FastAPI

from fastapi_filebased_routing import create_router_from_path

ROUTES_DIR = Path(__file__).parent / "routes"


def create_app(routes_dir: Path = ROUTES_DIR) -> FastAPI:
    """Build a FastAPI instance wired to the given routes directory."""
    application = FastAPI(title="Concurrency Test App")
    router = create_router_from_path(routes_dir)
    application.include_router(router)
    return application


app = create_app()
