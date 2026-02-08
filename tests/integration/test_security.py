"""Integration tests for security validation through the full pipeline.

Tests verify that create_router_from_path() enforces security boundaries
at every layer: scanner (directory traversal, symlinks, hidden dirs),
parser (parameter name validation), and importer (path validation).

Each test exercises the complete pipeline, not individual modules.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_filebased_routing import create_router_from_path
from fastapi_filebased_routing.exceptions import (
    PathParseError,
)

VALID_HANDLER = 'def get():\n    return {"ok": True}\n'


class TestPathTraversalBlocked:
    """Path traversal via '..' patterns in directory names is blocked."""

    def test_directory_starting_with_double_dot_silently_skipped(self, tmp_path: Path):
        """A directory named '..escape' is silently skipped by the scanner.

        The filesystem allows directory names starting with '..' (unlike
        the literal '..' entry). The scanner's hidden directory filter
        catches these because '..' starts with '.', preventing any
        path traversal attempt from reaching the parser or importer.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Create a valid route so we confirm the base dir works
        valid_dir = route_dir / "health"
        valid_dir.mkdir()
        (valid_dir / "route.py").write_text(
            'def get():\n    return {"healthy": True}\n'
        )

        # Create a directory starting with '..' - valid filesystem name,
        # but scanner skips it via the hidden directory filter
        traversal_dir = route_dir / "..escape"
        traversal_dir.mkdir()
        (traversal_dir / "route.py").write_text(VALID_HANDLER)

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Only the valid route is registered
        assert client.get("/health").status_code == 200

        # The dot-prefixed directory route is not registered
        http_routes = [r for r in router.routes if hasattr(r, "methods")]
        assert len(http_routes) == 1

    def test_directory_named_triple_dot_silently_skipped(self, tmp_path: Path):
        """Directory names starting with dots are silently skipped.

        Names like '...config' or '.foo' are caught by the scanner's
        hidden directory filter (starts with '.') before the parser
        ever sees them. This prevents traversal-like patterns from
        reaching deeper layers.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Triple-dot directory is caught by hidden dir filter
        bad_dir = route_dir / "...config"
        bad_dir.mkdir()
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        router = create_router_from_path(route_dir)

        # No routes registered from dot-prefixed directory
        assert len(router.routes) == 0

    def test_symlink_based_traversal_outside_base_is_skipped(self, tmp_path: Path):
        """Symlink-based path traversal that resolves outside base is blocked.

        Even if a symlink points to a parent directory, the scanner
        resolves the symlink and verifies the target is within the base.
        This is the real-world path traversal protection mechanism.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # External directory simulating a traversal target
        external_dir = tmp_path / "sensitive"
        external_dir.mkdir()
        (external_dir / "route.py").write_text(
            'def get():\n    return {"leaked": True}\n'
        )

        # Symlink that effectively performs path traversal
        traversal_link = route_dir / "escape"
        traversal_link.symlink_to(external_dir)

        # Scanner resolves the symlink, sees it's outside base, and skips it
        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)

        # No routes registered since the only route.py was via symlink outside base
        assert len(router.routes) == 0


class TestSymlinkOutsideBaseRejected:
    """Symlinks pointing outside the base directory are rejected."""

    def test_symlink_to_external_directory_skipped(self, tmp_path: Path):
        """A symlink pointing outside the base directory is silently skipped.

        The scanner resolves symlinks before checking containment.
        Routes from symlinks that resolve outside base are not registered.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        external_dir = tmp_path / "external"
        external_dir.mkdir()
        (external_dir / "route.py").write_text(VALID_HANDLER)

        symlink = route_dir / "evil"
        symlink.symlink_to(external_dir)

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)

        # The symlinked route should not be registered
        assert len(router.routes) == 0

    def test_symlink_to_external_file_skipped(self, tmp_path: Path):
        """A symlinked route.py file pointing outside base is skipped.

        Even if only the route.py file itself is symlinked (not the
        directory), the resolved path is checked against the base.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Create route.py outside the base
        external_dir = tmp_path / "outside"
        external_dir.mkdir()
        external_route = external_dir / "route.py"
        external_route.write_text(VALID_HANDLER)

        # Create directory inside base but symlink the route.py file
        inner_dir = route_dir / "sneaky"
        inner_dir.mkdir()
        symlinked_file = inner_dir / "route.py"
        symlinked_file.symlink_to(external_route)

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)

        # Route file resolves outside base, should not be registered
        assert len(router.routes) == 0

    def test_deeply_nested_symlink_outside_base_skipped(self, tmp_path: Path):
        """Deeply nested symlink chain that ultimately escapes base is skipped."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Create external target
        external_dir = tmp_path / "outside" / "deep" / "secret"
        external_dir.mkdir(parents=True)
        (external_dir / "route.py").write_text(VALID_HANDLER)

        # Nested path inside base that links out
        nested = route_dir / "api" / "v1"
        nested.mkdir(parents=True)
        link = nested / "data"
        link.symlink_to(external_dir)

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # The linked route must not be reachable
        response = client.get("/api/v1/data")
        assert response.status_code == 404

    def test_mixed_valid_and_external_symlink_only_valid_registered(
        self, tmp_path: Path
    ):
        """When valid routes and external symlinks coexist, only valid ones register."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Valid route inside base
        valid_dir = route_dir / "health"
        valid_dir.mkdir()
        (valid_dir / "route.py").write_text(
            'def get():\n    return {"status": "healthy"}\n'
        )

        # External symlink
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        (external_dir / "route.py").write_text(
            'def get():\n    return {"leaked": True}\n'
        )
        symlink = route_dir / "leaked"
        symlink.symlink_to(external_dir)

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Valid route works
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

        # Symlinked route does not exist
        response = client.get("/leaked")
        assert response.status_code == 404


class TestSymlinkInsideBaseAllowed:
    """Symlinks pointing inside the base directory are valid use cases."""

    def test_symlinked_directory_inside_base_not_traversed(self, tmp_path: Path):
        """Symlinked directories inside base are not traversed by rglob.

        Python 3.13 pathlib.Path.rglob does not follow directory
        symlinks by default. This means a symlinked directory pointing
        to another directory inside base will NOT have its route.py
        discovered. This is a known platform behavior, not a security
        block -- but it means the original route works while the
        symlink alias does not.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Create the actual route
        real_dir = route_dir / "users"
        real_dir.mkdir()
        (real_dir / "route.py").write_text(
            'def get():\n    return {"source": "users"}\n'
        )

        # Symlink inside the same base (directory-level)
        alias_dir = route_dir / "people"
        alias_dir.symlink_to(real_dir)

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Original route works
        response_users = client.get("/users")
        assert response_users.status_code == 200

        # Symlinked directory is NOT traversed by rglob in Python 3.13
        response_people = client.get("/people")
        assert response_people.status_code == 404

    def test_symlink_to_file_inside_base_allowed(self, tmp_path: Path):
        """A symlinked route.py file that resolves inside base is allowed."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Create the actual route file in a shared location
        shared_dir = route_dir / "shared"
        shared_dir.mkdir()
        shared_route = shared_dir / "route.py"
        shared_route.write_text(
            'def get():\n    return {"shared": True}\n'
        )

        # Create another directory that symlinks the route.py
        alias_dir = route_dir / "alias"
        alias_dir.mkdir()
        (alias_dir / "route.py").symlink_to(shared_route)

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Both paths should work since symlink target is inside base
        response_shared = client.get("/shared")
        assert response_shared.status_code == 200

        response_alias = client.get("/alias")
        assert response_alias.status_code == 200


class TestParameterNameInjectionPrevented:
    """Invalid Python identifiers are rejected as parameter names."""

    def test_parameter_starting_with_digit_rejected(self, tmp_path: Path):
        """Parameter names starting with a digit are rejected.

        Directory [123] is not a valid Python identifier and would
        cause issues as a function parameter name.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "users" / "[123]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)

    def test_parameter_with_hyphen_rejected(self, tmp_path: Path):
        """Parameter names with hyphens are rejected.

        Hyphens are not valid in Python identifiers, so [user-id] is
        rejected even though it looks reasonable as a URL parameter.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "users" / "[user-id]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)

    def test_parameter_with_spaces_rejected(self, tmp_path: Path):
        """Parameter names with spaces are rejected."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "[user id]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)

    def test_parameter_with_special_characters_rejected(self, tmp_path: Path):
        """Parameter names with special characters like $ are rejected."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "[user$id]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)

    def test_empty_parameter_name_rejected(self, tmp_path: Path):
        """Empty parameter name [] is rejected."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "[]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)

    def test_optional_parameter_with_invalid_name_rejected(self, tmp_path: Path):
        """Optional parameter with invalid name [[123]] is rejected."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "[[123bad]]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)

    def test_catch_all_parameter_with_invalid_name_rejected(self, tmp_path: Path):
        """Catch-all parameter with invalid name [...123] is rejected."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "[...123bad]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)

    def test_valid_parameter_names_accepted(self, tmp_path: Path):
        """Valid Python identifier parameter names are accepted.

        Confirms that legitimate parameter names pass through the
        full pipeline without issues.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        valid_dir = route_dir / "users" / "[user_id]"
        valid_dir.mkdir(parents=True)
        (valid_dir / "route.py").write_text(
            'def get(user_id: str):\n    return {"user_id": user_id}\n'
        )

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/users/abc123")
        assert response.status_code == 200
        assert response.json() == {"user_id": "abc123"}

    def test_uppercase_parameter_name_rejected(self, tmp_path: Path):
        """Uppercase characters in parameter names are rejected.

        The parser enforces lowercase-only identifiers for consistency.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        bad_dir = route_dir / "[UserId]"
        bad_dir.mkdir(parents=True)
        (bad_dir / "route.py").write_text(VALID_HANDLER)

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(route_dir)


class TestNonRouteFilesIgnored:
    """Non-route.py files in route directories are ignored."""

    def test_helper_file_in_route_directory_ignored(self, tmp_path: Path):
        """helper.py in a route directory is not treated as a route."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        users_dir = route_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text(VALID_HANDLER)
        (users_dir / "helper.py").write_text(
            'def compute():\n    return 42\n'
        )

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Only route.py handler is registered
        response = client.get("/users")
        assert response.status_code == 200

        # Verify only one route registered (GET /users)
        http_routes = [
            r for r in router.routes if hasattr(r, "methods")
        ]
        assert len(http_routes) == 1

    def test_utils_and_models_files_ignored(self, tmp_path: Path):
        """Various non-route.py files are all ignored."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        api_dir = route_dir / "api"
        api_dir.mkdir()
        (api_dir / "route.py").write_text(VALID_HANDLER)
        (api_dir / "utils.py").write_text('CONSTANT = "value"\n')
        (api_dir / "models.py").write_text('class User: pass\n')
        (api_dir / "schemas.py").write_text('SCHEMA = {}\n')

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api")
        assert response.status_code == 200

        # Only one route registered despite multiple .py files
        http_routes = [
            r for r in router.routes if hasattr(r, "methods")
        ]
        assert len(http_routes) == 1

    def test_python_file_named_get_py_ignored(self, tmp_path: Path):
        """A file named get.py (not route.py) is ignored.

        Only files named exactly 'route.py' are discovered.
        """
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        users_dir = route_dir / "users"
        users_dir.mkdir()
        # This is NOT a route file despite containing handler-like content
        (users_dir / "get.py").write_text(VALID_HANDLER)

        router = create_router_from_path(route_dir)

        # No routes registered because there is no route.py
        assert len(router.routes) == 0

    def test_route_txt_file_ignored(self, tmp_path: Path):
        """A file named route.txt is not treated as a route."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        users_dir = route_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.txt").write_text(VALID_HANDLER)

        router = create_router_from_path(route_dir)

        assert len(router.routes) == 0


class TestHiddenDirectoriesSkipped:
    """Directories starting with '.' are skipped during scanning."""

    def test_dotfile_directory_skipped(self, tmp_path: Path):
        """A directory named '.hidden' is skipped by the scanner."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Hidden directory with a route
        hidden_dir = route_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "route.py").write_text(VALID_HANDLER)

        router = create_router_from_path(route_dir)

        # No routes registered from hidden directory
        assert len(router.routes) == 0

    def test_dot_git_directory_skipped(self, tmp_path: Path):
        """A .git directory is skipped (common VCS directory)."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        git_dir = route_dir / ".git"
        git_dir.mkdir()
        (git_dir / "route.py").write_text(VALID_HANDLER)

        router = create_router_from_path(route_dir)

        assert len(router.routes) == 0

    def test_nested_hidden_directory_skipped(self, tmp_path: Path):
        """A hidden directory nested inside a valid directory is skipped."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Valid parent with hidden child
        api_dir = route_dir / "api"
        api_dir.mkdir()
        (api_dir / "route.py").write_text(
            'def get():\n    return {"api": True}\n'
        )

        hidden_child = api_dir / ".internal"
        hidden_child.mkdir()
        (hidden_child / "route.py").write_text(
            'def get():\n    return {"hidden": True}\n'
        )

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Valid route works
        response = client.get("/api")
        assert response.status_code == 200
        assert response.json() == {"api": True}

        # Hidden route does not exist
        response = client.get("/api/.internal")
        assert response.status_code == 404

    def test_mixed_visible_and_hidden_directories(self, tmp_path: Path):
        """Only visible directories have routes registered."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        # Visible routes
        (route_dir / "health").mkdir()
        (route_dir / "health" / "route.py").write_text(
            'def get():\n    return {"healthy": True}\n'
        )

        (route_dir / "users").mkdir()
        (route_dir / "users" / "route.py").write_text(
            'def get():\n    return {"users": []}\n'
        )

        # Hidden routes (should be skipped)
        (route_dir / ".debug").mkdir()
        (route_dir / ".debug" / "route.py").write_text(
            'def get():\n    return {"debug": True}\n'
        )

        (route_dir / ".config").mkdir()
        (route_dir / ".config" / "route.py").write_text(
            'def get():\n    return {"config": True}\n'
        )

        router = create_router_from_path(route_dir)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Visible routes registered
        assert client.get("/health").status_code == 200
        assert client.get("/users").status_code == 200

        # Hidden routes not registered
        assert client.get("/.debug").status_code == 404
        assert client.get("/.config").status_code == 404

    def test_pycache_directory_skipped(self, tmp_path: Path):
        """__pycache__ directories are skipped (Python bytecode cache)."""
        route_dir = tmp_path / "routes"
        route_dir.mkdir()

        pycache_dir = route_dir / "__pycache__"
        pycache_dir.mkdir()
        # Unlikely scenario but defensive: route.py in __pycache__
        (pycache_dir / "route.py").write_text(VALID_HANDLER)

        router = create_router_from_path(route_dir)

        assert len(router.routes) == 0
