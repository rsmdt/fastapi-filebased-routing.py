"""Shared fixtures for concurrency integration tests.

Provides the FastAPI test app built from the fixture directory at
tests/integration/fixtures/concurrency_app/.  Each test gets a fresh
copy of the routes in tmp_path for import isolation.

App structure:
    routes/_middleware.py                    # Root: stamps X-Request-ID, inits trace
    routes/echo/route.py                    # Echo: root middleware only
    routes/api/_middleware.py                # API dir: appends "api" to trace
    routes/api/users/route.py               # Users: file-level middleware
    routes/api/items/[item_id]/route.py     # Items: handler-level middleware via route()
    routes/api/protected/_middleware.py      # Auth: short-circuits 401
    routes/api/protected/route.py           # Protected: returns authenticated user
    routes/api/messages/route.py            # Messages: POST with JSON body
    routes/api/tasks/[task_id]/route.py     # Tasks: raises 404 for "missing-*" IDs
"""

import importlib.util
import shutil
from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi import FastAPI

CONCURRENT_REQUESTS = 50

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "app"

EXPECTED_TRACES = {
    "echo": ["root"],
    "users": ["root", "api", "users-file"],
    "items": ["root", "api", "items-handler"],
    "protected": ["root", "api", "auth"],
    "messages": ["root", "api", "messages-file"],
    "tasks": ["root", "api"],
}


def _load_create_app() -> Callable[..., FastAPI]:
    """Import create_app from the fixture's main.py by file path."""
    spec = importlib.util.spec_from_file_location("concurrency_app.main", FIXTURE_DIR / "main.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.create_app  # type: ignore[no-any-return]


_create_app = _load_create_app()


@pytest.fixture
def app(tmp_path: Path) -> FastAPI:
    """Build a fresh FastAPI instance with routes copied into tmp_path."""
    routes_dir = tmp_path / "routes"
    shutil.copytree(FIXTURE_DIR / "routes", routes_dir)
    return _create_app(routes_dir)
