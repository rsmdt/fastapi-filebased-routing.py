"""Executable docs: every shipped example must build a real router.

The ``examples/{basic,middleware,advanced}`` projects are documentation. These
tests exercise their actual route trees through the public API so the examples
cannot silently drift away from the library (pattern from Litestar/httpx, which
run their documentation examples as tests).
"""

from pathlib import Path

import pytest

from fastapi_filebased_routing import create_router_from_path

_EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
_EXAMPLES = ["basic", "middleware", "advanced"]


@pytest.mark.parametrize("example", _EXAMPLES)
def test_example_route_tree_builds(example: str) -> None:
    """Each example's app/ tree builds an APIRouter with at least one route.

    Uses an absolute path so module names stay unique per example (avoiding
    cross-example collisions in the import cache).
    """
    app_dir = _EXAMPLES_DIR / example / "app"
    assert app_dir.is_dir(), f"missing example app directory: {app_dir}"

    router = create_router_from_path(app_dir)

    registered_paths = [getattr(route, "path", None) for route in router.routes]
    assert any(registered_paths), f"example {example!r} produced no routes"
