"""Shared pytest fixtures for fastapi-filebased-routing tests."""

from pathlib import Path
from typing import Any

import pytest


@pytest.fixture
def create_route_file(tmp_path: Path):
    """Create a route.py file with given content in a directory.

    Returns a callable that accepts:
    - parent_dir: Path to parent directory (defaults to tmp_path)
    - content: Python code as string
    - subdir: Optional subdirectory name (e.g., "users" or "api/v1")

    Returns the Path to the created route.py file.
    """

    def _create(
        content: str,
        parent_dir: Path | None = None,
        subdir: str = "",
    ) -> Path:
        base = parent_dir or tmp_path
        if subdir:
            target_dir = base / subdir
            target_dir.mkdir(parents=True, exist_ok=True)
        else:
            target_dir = base

        route_file = target_dir / "route.py"
        route_file.write_text(content)
        return route_file

    return _create


@pytest.fixture
def create_route_tree(tmp_path: Path, create_route_file):
    """Create a directory tree with route.py files from a dict specification.

    Accepts a dict where:
    - Keys are directory paths (e.g., "users", "api/v1", "[userId]")
    - Values are either:
      - str: content for route.py in that directory
      - dict: nested subdirectories

    Example:
        {
            "users": "def get(): return {'users': []}",
            "posts": {
                "[postId]": "def get(postId: int): return {'id': postId}"
            }
        }

    Returns the tmp_path root containing the tree.
    """

    def _create(spec: dict[str, Any], parent_dir: Path | None = None) -> Path:
        base = parent_dir or tmp_path

        for key, value in spec.items():
            if isinstance(value, str):
                # Leaf node: create route.py with content
                create_route_file(content=value, parent_dir=base, subdir=key)
            elif isinstance(value, dict):
                # Branch node: recurse
                subdir = base / key
                subdir.mkdir(parents=True, exist_ok=True)
                _create(value, parent_dir=subdir)
            else:
                msg = f"Invalid spec value type: {type(value)}"
                raise TypeError(msg)

        return base

    return _create


@pytest.fixture
def simple_route_handler() -> str:
    """Return a minimal valid route handler for testing."""
    return """
def get():
    return {"message": "Hello, World!"}
"""


@pytest.fixture
def async_route_handler() -> str:
    """Return a minimal async route handler for testing."""
    return """
async def get():
    return {"message": "Async Hello!"}
"""


@pytest.fixture
def multi_method_handler() -> str:
    """Return a route handler with multiple HTTP methods."""
    return """
def get():
    return {"method": "GET"}

def post(data: dict):
    return {"method": "POST", "data": data}

def delete():
    return {"method": "DELETE"}
"""


@pytest.fixture
def websocket_handler() -> str:
    """Return a WebSocket handler for testing."""
    return """
async def websocket(websocket):
    await websocket.accept()
    await websocket.send_json({"message": "Connected"})
    await websocket.close()
"""


@pytest.fixture
def parametric_route_handler() -> str:
    """Return a route handler with path parameters."""
    return """
def get(user_id: int):
    return {"user_id": user_id}
"""
