"""Tests for core scanner module."""

from pathlib import Path

import pytest

from fastapi_filebased_routing.core.parser import SegmentType
from fastapi_filebased_routing.core.scanner import RouteDefinition, scan_routes
from fastapi_filebased_routing.exceptions import RouteDiscoveryError


class TestRouteDefinition:
    """Test RouteDefinition dataclass and properties."""

    def test_route_definition_frozen(self):
        """RouteDefinition instances are immutable."""
        from fastapi_filebased_routing.core.parser import PathSegment

        rd = RouteDefinition(
            path="/users",
            file_path=Path("/app/users/route.py"),
            segments=tuple(
                [PathSegment(name="users", segment_type=SegmentType.STATIC, original="users")]
            ),
        )

        with pytest.raises((AttributeError, TypeError)):
            rd.path = "/new"  # type: ignore[misc]

    def test_has_optional_params_true(self):
        """has_optional_params returns True when optional segments present."""
        from fastapi_filebased_routing.core.parser import PathSegment

        rd = RouteDefinition(
            path="/api/{version}/users",
            file_path=Path("/route.py"),
            segments=tuple(
                [
                    PathSegment(name="api", segment_type=SegmentType.STATIC, original="api"),
                    PathSegment(
                        name="version", segment_type=SegmentType.OPTIONAL, original="[[version]]"
                    ),
                    PathSegment(name="users", segment_type=SegmentType.STATIC, original="users"),
                ]
            ),
        )

        assert rd.has_optional_params is True

    def test_has_optional_params_false(self):
        """has_optional_params returns False when no optional segments."""
        from fastapi_filebased_routing.core.parser import PathSegment

        rd = RouteDefinition(
            path="/users/{id}",
            file_path=Path("/route.py"),
            segments=tuple(
                [
                    PathSegment(name="users", segment_type=SegmentType.STATIC, original="users"),
                    PathSegment(name="id", segment_type=SegmentType.DYNAMIC, original="[id]"),
                ]
            ),
        )

        assert rd.has_optional_params is False

    def test_parameters_property(self):
        """parameters property returns only parameter segments."""
        from fastapi_filebased_routing.core.parser import PathSegment

        rd = RouteDefinition(
            path="/workspaces/{workspace_id}/projects/{project_id}",
            file_path=Path("/route.py"),
            segments=tuple(
                [
                    PathSegment(
                        name="workspaces", segment_type=SegmentType.STATIC, original="workspaces"
                    ),
                    PathSegment(
                        name="workspace_id",
                        segment_type=SegmentType.DYNAMIC,
                        original="[workspace_id]",
                    ),
                    PathSegment(
                        name="projects", segment_type=SegmentType.STATIC, original="projects"
                    ),
                    PathSegment(
                        name="project_id",
                        segment_type=SegmentType.DYNAMIC,
                        original="[project_id]",
                    ),
                ]
            ),
        )

        params = rd.parameters
        assert len(params) == 2
        assert params[0].name == "workspace_id"
        assert params[1].name == "project_id"


class TestScanRoutes:
    """Test route discovery functionality."""

    def test_finds_root_route_file(self, tmp_path: Path):
        """Root-level route.py maps to /."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 1
        assert routes[0].path == "/"
        assert routes[0].file_path == route_file

    def test_finds_nested_route_file(self, tmp_path: Path):
        """Nested route files are discovered with correct paths."""
        api_dir = tmp_path / "api" / "v1" / "projects"
        api_dir.mkdir(parents=True)
        route_file = api_dir / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 1
        assert routes[0].path == "/api/v1/projects"
        assert routes[0].file_path == route_file

    def test_finds_route_with_dynamic_parameter(self, tmp_path: Path):
        """Dynamic parameters are parsed correctly."""
        project_dir = tmp_path / "api" / "v1" / "projects" / "[project_id]"
        project_dir.mkdir(parents=True)
        route_file = project_dir / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 1
        assert routes[0].path == "/api/v1/projects/{project_id}"
        assert routes[0].segments[-1].segment_type == SegmentType.DYNAMIC
        assert routes[0].segments[-1].name == "project_id"

    def test_finds_multiple_route_files(self, tmp_path: Path):
        """Multiple route files are all discovered."""
        (tmp_path / "projects").mkdir()
        (tmp_path / "projects" / "route.py").write_text("async def get(): pass")
        (tmp_path / "users").mkdir()
        (tmp_path / "users" / "route.py").write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 2
        paths = {r.path for r in routes}
        assert "/projects" in paths
        assert "/users" in paths

    def test_route_group_excluded_from_path(self, tmp_path: Path):
        """Route groups are excluded from URL paths."""
        health_dir = tmp_path / "(public)" / "health"
        health_dir.mkdir(parents=True)
        route_file = health_dir / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 1
        assert routes[0].path == "/health"

    def test_skips_pycache_directories(self, tmp_path: Path):
        """__pycache__ directories are skipped."""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "route.py").write_text("async def get(): pass")

        # Create a valid route
        (tmp_path / "valid").mkdir()
        (tmp_path / "valid" / "route.py").write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 1
        assert routes[0].path == "/valid"

    def test_skips_hidden_directories(self, tmp_path: Path):
        """Hidden directories (starting with .) are skipped."""
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "route.py").write_text("async def get(): pass")

        # Create a valid route
        (tmp_path / "valid").mkdir()
        (tmp_path / "valid" / "route.py").write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 1
        assert routes[0].path == "/valid"

    def test_empty_directory_no_routes(self, tmp_path: Path):
        """Empty directory returns empty list."""
        routes = scan_routes(tmp_path)
        assert routes == []

    def test_directory_without_route_py(self, tmp_path: Path):
        """Directories without route.py are ignored."""
        (tmp_path / "users").mkdir()
        (tmp_path / "users" / "other.py").write_text("# Not a route")

        routes = scan_routes(tmp_path)
        assert routes == []

    def test_raises_error_for_nonexistent_path(self, tmp_path: Path):
        """Nonexistent base path raises RouteDiscoveryError."""
        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(RouteDiscoveryError, match="does not exist"):
            scan_routes(nonexistent)

    def test_raises_error_for_file_not_directory(self, tmp_path: Path):
        """File path (not directory) raises RouteDiscoveryError."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")
        with pytest.raises(RouteDiscoveryError, match="not a directory"):
            scan_routes(file_path)

    def test_accepts_string_path(self, tmp_path: Path):
        """scan_routes accepts string paths."""
        (tmp_path / "users").mkdir()
        (tmp_path / "users" / "route.py").write_text("async def get(): pass")

        routes = scan_routes(str(tmp_path))

        assert len(routes) == 1
        assert routes[0].path == "/users"


class TestOptionalParameterVariants:
    """Test optional parameter variant generation."""

    def test_no_optional_params_single_variant(self, tmp_path: Path):
        """No optional parameters produces single route."""
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        route_file = users_dir / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 1
        assert routes[0].path == "/users"

    def test_single_optional_param_two_variants(self, tmp_path: Path):
        """Single optional parameter generates 2 variants."""
        version_dir = tmp_path / "api" / "[[version]]" / "projects"
        version_dir.mkdir(parents=True)
        route_file = version_dir / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 2
        paths = {r.path for r in routes}
        assert "/api/projects" in paths
        assert "/api/{version}/projects" in paths

        # All variants point to same file
        assert all(r.file_path == route_file for r in routes)

    def test_two_optional_params_four_variants(self, tmp_path: Path):
        """Two optional parameters generate 4 variants (2^2)."""
        nested = tmp_path / "[[a]]" / "[[b]]" / "items"
        nested.mkdir(parents=True)
        route_file = nested / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 4  # 2^2 = 4 variants
        paths = {r.path for r in routes}
        assert "/items" in paths
        assert "/{a}/items" in paths
        assert "/{b}/items" in paths
        assert "/{a}/{b}/items" in paths

        # All variants point to same file
        assert all(r.file_path == route_file for r in routes)

    def test_optional_mixed_with_static_and_dynamic(self, tmp_path: Path):
        """Optional parameters work with static and dynamic segments."""
        complex_dir = tmp_path / "api" / "[[version]]" / "users" / "[user_id]"
        complex_dir.mkdir(parents=True)
        route_file = complex_dir / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        assert len(routes) == 2
        paths = {r.path for r in routes}
        assert "/api/users/{user_id}" in paths
        assert "/api/{version}/users/{user_id}" in paths

    def test_variant_with_optional_has_correct_segments(self, tmp_path: Path):
        """Variants include/exclude optional segments correctly."""
        version_dir = tmp_path / "api" / "[[version]]"
        version_dir.mkdir(parents=True)
        route_file = version_dir / "route.py"
        route_file.write_text("async def get(): pass")

        routes = scan_routes(tmp_path)

        # Find the variant without optional param
        variant_without = [r for r in routes if r.path == "/api"][0]
        assert len(variant_without.segments) == 1
        assert variant_without.segments[0].name == "api"

        # Find the variant with optional param
        variant_with = [r for r in routes if r.path == "/api/{version}"][0]
        assert len(variant_with.segments) == 2
        assert variant_with.segments[0].name == "api"
        assert variant_with.segments[1].name == "version"


class TestSymlinkSecurity:
    """Test symlink security validation."""

    def test_skips_symlink_outside_base_path(self, tmp_path: Path):
        """Symlinks pointing outside base path are rejected."""
        # Create a directory outside the base
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        external_route = external_dir / "route.py"
        external_route.write_text("async def get(): return {'hacked': True}")

        # Create base directory with symlink to external
        base_dir = tmp_path / "app"
        base_dir.mkdir()
        symlink_dir = base_dir / "evil"
        symlink_dir.symlink_to(external_dir)

        # Create a valid route
        (base_dir / "valid").mkdir()
        (base_dir / "valid" / "route.py").write_text("async def get(): pass")

        routes = scan_routes(base_dir)

        # Should only find the valid route, not the symlinked one
        assert len(routes) == 1
        assert routes[0].path == "/valid"

    def test_allows_symlink_within_base_path(self, tmp_path: Path):
        """Symlinks within base path are allowed."""
        # Create directory structure
        base_dir = tmp_path / "app"
        (base_dir / "routes").mkdir(parents=True)
        route_file = base_dir / "routes" / "route.py"
        route_file.write_text("async def get(): pass")

        # Create symlink to directory within base
        (base_dir / "alias").symlink_to(base_dir / "routes")

        routes = scan_routes(base_dir)

        # Both the original and symlinked route should be found
        paths = {r.path for r in routes}
        assert "/routes" in paths


class TestMiddlewareDiscovery:
    """Test _middleware.py file discovery functionality."""

    def test_discovers_middleware_in_base_directory(self, tmp_path: Path):
        """_middleware.py in base directory is discovered with depth 0."""
        middleware_file = tmp_path / "_middleware.py"
        middleware_file.write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(tmp_path)

        assert len(files) == 1
        assert files[0].file_path == middleware_file
        assert files[0].directory == tmp_path
        assert files[0].depth == 0

    def test_discovers_middleware_in_nested_directories(self, tmp_path: Path):
        """_middleware.py in nested directories discovered with correct depth."""
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "_middleware.py").write_text("middleware = []")
        (tmp_path / "api" / "v1").mkdir()
        (tmp_path / "api" / "v1" / "_middleware.py").write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(tmp_path)

        assert len(files) == 2
        # Should be sorted by depth (shallowest first)
        assert files[0].depth == 1  # api/_middleware.py
        assert files[1].depth == 2  # api/v1/_middleware.py

    def test_multiple_middleware_sorted_by_depth(self, tmp_path: Path):
        """Multiple _middleware.py at different levels sorted by depth."""
        # Create middleware at root, depth 1, and depth 2
        (tmp_path / "_middleware.py").write_text("middleware = []")
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "_middleware.py").write_text("middleware = []")
        (tmp_path / "api" / "v1").mkdir()
        (tmp_path / "api" / "v1" / "_middleware.py").write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(tmp_path)

        assert len(files) == 3
        assert files[0].depth == 0  # root
        assert files[1].depth == 1  # api
        assert files[2].depth == 2  # api/v1
        # Verify they're in correct order
        assert files[0].directory == tmp_path
        assert files[1].directory == tmp_path / "api"
        assert files[2].directory == tmp_path / "api" / "v1"

    def test_skips_pycache_directories_middleware(self, tmp_path: Path):
        """__pycache__ directories are skipped when scanning for middleware."""
        pycache = tmp_path / "__pycache__"
        pycache.mkdir()
        (pycache / "_middleware.py").write_text("middleware = []")

        # Create a valid middleware file
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "_middleware.py").write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(tmp_path)

        assert len(files) == 1
        assert files[0].directory == tmp_path / "api"

    def test_skips_hidden_directories_middleware(self, tmp_path: Path):
        """Hidden directories (starting with .) are skipped."""
        hidden = tmp_path / ".hidden"
        hidden.mkdir()
        (hidden / "_middleware.py").write_text("middleware = []")

        # Create a valid middleware file
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "_middleware.py").write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(tmp_path)

        assert len(files) == 1
        assert files[0].directory == tmp_path / "api"

    def test_rejects_symlink_outside_base_path_middleware(self, tmp_path: Path):
        """Symlinks pointing outside base path are rejected for middleware."""
        # Create a directory outside the base
        external_dir = tmp_path / "external"
        external_dir.mkdir()
        external_mw = external_dir / "_middleware.py"
        external_mw.write_text("middleware = []")

        # Create base directory with symlink to external
        base_dir = tmp_path / "app"
        base_dir.mkdir()
        symlink_dir = base_dir / "evil"
        symlink_dir.symlink_to(external_dir)

        # Create a valid middleware file
        (base_dir / "api").mkdir()
        (base_dir / "api" / "_middleware.py").write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(base_dir)

        # Should only find the valid middleware, not the symlinked one
        assert len(files) == 1
        assert files[0].directory == base_dir / "api"

    def test_no_middleware_files_returns_empty_list(self, tmp_path: Path):
        """No _middleware.py files returns empty list."""
        (tmp_path / "api").mkdir()
        (tmp_path / "api" / "users").mkdir()

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(tmp_path)
        assert files == []

    def test_middleware_inside_route_groups(self, tmp_path: Path):
        """_middleware.py inside route groups (name) discovered with correct depth."""
        admin_group = tmp_path / "(admin)"
        admin_group.mkdir()
        (admin_group / "_middleware.py").write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(tmp_path)

        assert len(files) == 1
        assert files[0].directory == admin_group
        assert files[0].depth == 1

    def test_accepts_string_path_middleware(self, tmp_path: Path):
        """scan_middleware accepts string paths."""
        (tmp_path / "_middleware.py").write_text("middleware = []")

        from fastapi_filebased_routing.core.scanner import scan_middleware

        files = scan_middleware(str(tmp_path))

        assert len(files) == 1
        assert files[0].directory == tmp_path

    def test_raises_error_for_nonexistent_path_middleware(self, tmp_path: Path):
        """Nonexistent base path raises RouteDiscoveryError."""
        from fastapi_filebased_routing.core.scanner import scan_middleware

        nonexistent = tmp_path / "does_not_exist"
        with pytest.raises(RouteDiscoveryError, match="does not exist"):
            scan_middleware(nonexistent)

    def test_raises_error_for_file_not_directory_middleware(self, tmp_path: Path):
        """File path (not directory) raises RouteDiscoveryError."""
        from fastapi_filebased_routing.core.scanner import scan_middleware

        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")
        with pytest.raises(RouteDiscoveryError, match="not a directory"):
            scan_middleware(file_path)
