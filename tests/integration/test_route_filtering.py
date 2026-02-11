"""End-to-end integration tests for route include/exclude filtering.

Tests the full pipeline with real directory structures, real imports,
and real HTTP requests via TestClient.
"""

import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_filebased_routing import RouteFilterError, create_router_from_path

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_route(base: Path, subdir: str, content: str) -> None:
    """Write a route.py file at base/subdir/route.py."""
    target = base / subdir if subdir != "." else base
    target.mkdir(parents=True, exist_ok=True)
    (target / "route.py").write_text(content)


def _write_middleware(base: Path, subdir: str, content: str) -> None:
    """Write a _middleware.py file at base/subdir/_middleware.py."""
    target = base / subdir if subdir != "." else base
    target.mkdir(parents=True, exist_ok=True)
    (target / "_middleware.py").write_text(content)


def _make_app(base: Path, **kwargs) -> TestClient:
    """Create a FastAPI app with file-based routing and return a TestClient."""
    router = create_router_from_path(base, **kwargs)
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


# ---------------------------------------------------------------------------
# Standard route tree used across test classes
# ---------------------------------------------------------------------------


@pytest.fixture
def route_tree(tmp_path: Path) -> Path:
    """Create a standard route tree for filtering tests.

    Structure:
        routes/
          _middleware.py           # adds X-Root header
          (public)/
            users/route.py         # GET /users
            health/route.py        # GET /health
          (admin)/
            _middleware.py          # adds X-Admin header
            settings/route.py      # GET /settings
            users/route.py         # GET /users (duplicate path via group)
    """
    base = tmp_path / "routes"
    base.mkdir()

    # Root middleware
    _write_middleware(
        base,
        ".",
        "async def middleware(request, call_next):\n"
        "    response = await call_next(request)\n"
        '    response.headers["X-Root"] = "applied"\n'
        "    return response\n",
    )

    # Public routes
    _write_route(
        base,
        "(public)/users",
        'def get():\n    return {"route": "public-users"}\n',
    )
    _write_route(
        base,
        "(public)/health",
        'def get():\n    return {"route": "health"}\n',
    )

    # Admin routes with middleware
    _write_middleware(
        base,
        "(admin)",
        "async def middleware(request, call_next):\n"
        "    response = await call_next(request)\n"
        '    response.headers["X-Admin"] = "applied"\n'
        "    return response\n",
    )
    _write_route(
        base,
        "(admin)/settings",
        'def get():\n    return {"route": "admin-settings"}\n',
    )

    return base


@pytest.fixture
def route_tree_no_dup(tmp_path: Path) -> Path:
    """Route tree without duplicate paths (no admin/users)."""
    base = tmp_path / "routes"
    base.mkdir()

    _write_middleware(
        base,
        ".",
        "async def middleware(request, call_next):\n"
        "    response = await call_next(request)\n"
        '    response.headers["X-Root"] = "applied"\n'
        "    return response\n",
    )

    _write_route(
        base,
        "(public)/users",
        'def get():\n    return {"route": "public-users"}\n',
    )
    _write_route(
        base,
        "(public)/health",
        'def get():\n    return {"route": "health"}\n',
    )

    _write_middleware(
        base,
        "(admin)",
        "async def middleware(request, call_next):\n"
        "    response = await call_next(request)\n"
        '    response.headers["X-Admin"] = "applied"\n'
        "    return response\n",
    )
    _write_route(
        base,
        "(admin)/settings",
        'def get():\n    return {"route": "admin-settings"}\n',
    )

    return base


# ---------------------------------------------------------------------------
# Include filtering
# ---------------------------------------------------------------------------


class TestIncludeFiltering:
    """Test include-based route filtering end-to-end."""

    def test_include_group_loads_only_matching_routes(self, route_tree_no_dup: Path) -> None:
        """Include by group name loads only that group's routes."""
        client = _make_app(route_tree_no_dup, include=["(public)"])

        assert client.get("/users").status_code == 200
        assert client.get("/users").json() == {"route": "public-users"}
        assert client.get("/health").status_code == 200

    def test_included_routes_exclude_other_groups(self, route_tree_no_dup: Path) -> None:
        """Routes from non-included groups return 404."""
        client = _make_app(route_tree_no_dup, include=["(public)"])

        assert client.get("/settings").status_code == 404

    def test_include_by_bare_name(self, route_tree_no_dup: Path) -> None:
        """Include by bare name matches that segment in any group."""
        client = _make_app(route_tree_no_dup, include=["settings"])

        assert client.get("/settings").status_code == 200
        assert client.get("/users").status_code == 404
        assert client.get("/health").status_code == 404


# ---------------------------------------------------------------------------
# Exclude filtering
# ---------------------------------------------------------------------------


class TestExcludeFiltering:
    """Test exclude-based route filtering end-to-end."""

    def test_exclude_group_removes_matching_routes(self, route_tree_no_dup: Path) -> None:
        """Exclude by group name removes that group's routes."""
        client = _make_app(route_tree_no_dup, exclude=["(admin)"])

        assert client.get("/users").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/settings").status_code == 404

    def test_exclude_by_bare_name(self, route_tree_no_dup: Path) -> None:
        """Exclude by bare name removes routes with that segment."""
        client = _make_app(route_tree_no_dup, exclude=["settings"])

        assert client.get("/users").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/settings").status_code == 404


# ---------------------------------------------------------------------------
# Middleware with filtering
# ---------------------------------------------------------------------------


class TestMiddlewareWithFiltering:
    """Test that middleware behaves correctly with filtered routes."""

    def test_ancestor_middleware_applies_to_included_routes(self, route_tree_no_dup: Path) -> None:
        """Root _middleware.py still applies when child routes are included."""
        client = _make_app(route_tree_no_dup, include=["(public)"])

        response = client.get("/users")
        assert response.status_code == 200
        assert response.headers["X-Root"] == "applied"

    def test_excluded_group_middleware_not_applied(self, route_tree_no_dup: Path) -> None:
        """Admin _middleware.py should not apply when admin is excluded."""
        client = _make_app(route_tree_no_dup, include=["(public)"])

        response = client.get("/users")
        assert "X-Admin" not in response.headers

    def test_included_group_gets_its_middleware(self, route_tree_no_dup: Path) -> None:
        """When including admin group, its middleware applies."""
        client = _make_app(route_tree_no_dup, include=["(admin)"])

        response = client.get("/settings")
        assert response.status_code == 200
        assert response.headers["X-Root"] == "applied"
        assert response.headers["X-Admin"] == "applied"


# ---------------------------------------------------------------------------
# Group-aware filtering
# ---------------------------------------------------------------------------


class TestGroupAwareFiltering:
    """Test that filtering works correctly with route groups."""

    def test_bare_name_matches_across_groups(self, tmp_path: Path) -> None:
        """Bare name 'health' matches across different groups."""
        base = tmp_path / "routes"
        base.mkdir()

        _write_route(
            base,
            "(public)/health",
            'def get():\n    return {"source": "public"}\n',
        )
        _write_route(
            base,
            "(internal)/status",
            'def get():\n    return {"source": "internal"}\n',
        )

        client = _make_app(base, include=["health"])

        assert client.get("/health").status_code == 200
        assert client.get("/status").status_code == 404

    def test_group_name_scopes_to_specific_group(self, tmp_path: Path) -> None:
        """Group name '(internal)' only scopes to that group."""
        base = tmp_path / "routes"
        base.mkdir()

        _write_route(
            base,
            "(public)/health",
            'def get():\n    return {"source": "public"}\n',
        )
        _write_route(
            base,
            "(internal)/status",
            'def get():\n    return {"source": "internal"}\n',
        )

        client = _make_app(base, include=["(internal)"])

        assert client.get("/status").status_code == 200
        assert client.get("/health").status_code == 404


# ---------------------------------------------------------------------------
# Deployment scenarios
# ---------------------------------------------------------------------------


class TestDeploymentScenarios:
    """Test real-world deployment topology scenarios."""

    def test_dmz_profile_includes_only_public(self, route_tree_no_dup: Path) -> None:
        """DMZ deployment: only public routes loaded."""
        client = _make_app(route_tree_no_dup, include=["(public)"])

        assert client.get("/users").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/settings").status_code == 404

    def test_admin_profile_excludes_public(self, route_tree_no_dup: Path) -> None:
        """Admin deployment: exclude public, keep admin."""
        client = _make_app(route_tree_no_dup, exclude=["(public)"])

        assert client.get("/settings").status_code == 200
        assert client.get("/users").status_code == 404
        assert client.get("/health").status_code == 404

    def test_dev_profile_no_filter(self, route_tree_no_dup: Path) -> None:
        """Development: no filters, everything loaded."""
        client = _make_app(route_tree_no_dup)

        assert client.get("/users").status_code == 200
        assert client.get("/health").status_code == 200
        assert client.get("/settings").status_code == 200

    def test_both_include_and_exclude_raises_error(self, route_tree_no_dup: Path) -> None:
        """Cannot use both include and exclude simultaneously."""
        with pytest.raises(RouteFilterError, match="Cannot specify both"):
            create_router_from_path(
                route_tree_no_dup,
                include=["(public)"],
                exclude=["(admin)"],
            )


# ---------------------------------------------------------------------------
# Module isolation: excluded code never imported
# ---------------------------------------------------------------------------


class TestModuleIsolation:
    """Verify excluded route modules are never imported into sys.modules."""

    def test_excluded_route_module_not_in_sys_modules(self, tmp_path: Path) -> None:
        """Excluded route.py is never imported (not in sys.modules)."""
        base = tmp_path / "routes"
        base.mkdir()

        _write_route(
            base,
            "included",
            'def get():\n    return {"ok": True}\n',
        )
        _write_route(
            base,
            "excluded",
            'def get():\n    return {"secret": True}\n',
        )

        # Clear any cached modules for this test
        excluded_route = base / "excluded" / "route.py"

        # Record modules before
        modules_before = set(sys.modules.keys())

        _make_app(base, exclude=["excluded"])

        # Check no new module was imported for the excluded route
        new_modules = set(sys.modules.keys()) - modules_before
        for mod_name in new_modules:
            mod = sys.modules.get(mod_name)
            if mod and hasattr(mod, "__file__") and mod.__file__:
                assert not mod.__file__.startswith(str(excluded_route)), (
                    f"Excluded module was imported: {mod_name}"
                )
