"""Unit tests for core route filtering module."""

from pathlib import Path

import pytest

from fastapi_filebased_routing.core.filter import (
    _matches_any_pattern,
    _relative_directory,
    compute_active_directories,
    filter_middleware_files,
    filter_routes,
    validate_filter_params,
)
from fastapi_filebased_routing.core.scanner import MiddlewareFile, RouteDefinition
from fastapi_filebased_routing.exceptions import RouteFilterError

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _route(base: Path, subdir: str) -> RouteDefinition:
    """Create a minimal RouteDefinition for testing."""
    file_path = base / "route.py" if subdir == "." else base / subdir / "route.py"
    return RouteDefinition(
        path=f"/{subdir}" if subdir != "." else "/",
        file_path=file_path,
        segments=(),
    )


def _mw_file(base: Path, subdir: str, depth: int) -> MiddlewareFile:
    """Create a minimal MiddlewareFile for testing."""
    directory = base if subdir == "." else base / subdir
    return MiddlewareFile(
        file_path=directory / "_middleware.py",
        directory=directory,
        depth=depth,
    )


# ---------------------------------------------------------------------------
# validate_filter_params
# ---------------------------------------------------------------------------


class TestValidateFilterParams:
    """Tests for validate_filter_params()."""

    def test_none_none_passes(self) -> None:
        """No filters provided is valid."""
        validate_filter_params(None, None)

    def test_include_only_passes(self) -> None:
        """Include-only is valid."""
        validate_filter_params(["users"], None)

    def test_exclude_only_passes(self) -> None:
        """Exclude-only is valid."""
        validate_filter_params(None, ["admin"])

    def test_both_non_empty_raises_route_filter_error(self) -> None:
        """Both include and exclude raises RouteFilterError."""
        with pytest.raises(RouteFilterError, match="Cannot specify both"):
            validate_filter_params(["users"], ["admin"])

    def test_empty_lists_pass(self) -> None:
        """Empty lists are treated the same as None."""
        validate_filter_params([], [])

    def test_include_empty_exclude_non_empty_passes(self) -> None:
        """Empty include with non-empty exclude is valid."""
        validate_filter_params([], ["admin"])

    def test_include_non_empty_exclude_empty_passes(self) -> None:
        """Non-empty include with empty exclude is valid."""
        validate_filter_params(["users"], [])


# ---------------------------------------------------------------------------
# _relative_directory
# ---------------------------------------------------------------------------


class TestRelativeDirectory:
    """Tests for _relative_directory()."""

    def test_root_returns_dot(self, tmp_path: Path) -> None:
        """Root route.py returns '.'."""
        result = _relative_directory(tmp_path / "route.py", tmp_path)
        assert result == "."

    def test_nested_returns_posix_path(self, tmp_path: Path) -> None:
        """Nested route returns posix-normalized relative path."""
        result = _relative_directory(tmp_path / "users" / "route.py", tmp_path)
        assert result == "users"

    def test_deeply_nested(self, tmp_path: Path) -> None:
        """Deeply nested route returns full posix path."""
        result = _relative_directory(tmp_path / "api" / "v1" / "users" / "route.py", tmp_path)
        assert result == "api/v1/users"

    def test_group_directory(self, tmp_path: Path) -> None:
        """Group directory preserved in path."""
        result = _relative_directory(tmp_path / "(admin)" / "settings" / "route.py", tmp_path)
        assert result == "(admin)/settings"


# ---------------------------------------------------------------------------
# _matches_any_pattern
# ---------------------------------------------------------------------------


class TestMatchesAnyPattern:
    """Tests for _matches_any_pattern()."""

    def test_glob_star_matches_everything(self) -> None:
        """Glob '*' matches everything including root '.'."""
        assert _matches_any_pattern(".", ["*"]) is True
        assert _matches_any_pattern("users", ["*"]) is True
        assert _matches_any_pattern("(admin)/settings", ["*"]) is True

    def test_bare_name_exact_segment_match(self) -> None:
        """Bare name matches exact segment."""
        assert _matches_any_pattern("users", ["users"]) is True

    def test_bare_name_segment_in_nested_path(self) -> None:
        """Bare name matches segment anywhere in path."""
        assert _matches_any_pattern("(public)/users", ["users"]) is True

    def test_bare_name_does_not_partial_match(self) -> None:
        """Bare name does NOT partial-match segments."""
        assert _matches_any_pattern("api2", ["api"]) is False
        assert _matches_any_pattern("userservice", ["users"]) is False

    def test_group_name_matches_group_dir(self) -> None:
        """Group name matches group directory."""
        assert _matches_any_pattern("(admin)/users", ["(admin)"]) is True
        assert _matches_any_pattern("(admin)", ["(admin)"]) is True

    def test_bare_name_transparent_to_groups(self) -> None:
        """Bare name 'users' matches across different groups."""
        assert _matches_any_pattern("(public)/users", ["users"]) is True
        assert _matches_any_pattern("(admin)/users", ["users"]) is True

    def test_root_dot_does_not_match_bare_names(self) -> None:
        """Root '.' does not match bare names."""
        assert _matches_any_pattern(".", ["users"]) is False
        assert _matches_any_pattern(".", ["(admin)"]) is False

    def test_no_match_returns_false(self) -> None:
        """No matching pattern returns False."""
        assert _matches_any_pattern("users", ["admin"]) is False
        assert _matches_any_pattern("api/v1", ["users"]) is False

    def test_glob_question_mark(self) -> None:
        """Glob '?' matches single character."""
        assert _matches_any_pattern("api", ["ap?"]) is True
        assert _matches_any_pattern("api", ["a??"]) is True

    def test_glob_bracket_pattern(self) -> None:
        """Glob bracket pattern matches character sets."""
        assert _matches_any_pattern("v1", ["v[0-9]"]) is True
        assert _matches_any_pattern("vx", ["v[0-9]"]) is False

    def test_bare_name_matches_descendants(self) -> None:
        """Bare name matches paths where name is ancestor segment."""
        assert _matches_any_pattern("users/[id]", ["users"]) is True
        assert _matches_any_pattern("api/users/[id]/posts", ["users"]) is True

    def test_deeply_nested_segment_match(self) -> None:
        """Bare name matches deeply nested paths."""
        assert _matches_any_pattern("api/v1/(public)/users", ["users"]) is True


# ---------------------------------------------------------------------------
# filter_routes
# ---------------------------------------------------------------------------


class TestFilterRoutes:
    """Tests for filter_routes()."""

    def test_no_filters_returns_all(self, tmp_path: Path) -> None:
        """No filters returns all routes unchanged."""
        routes = [_route(tmp_path, "users"), _route(tmp_path, "admin")]
        result = filter_routes(routes, base_path=tmp_path, include=None, exclude=None)
        assert result == routes

    def test_empty_include_exclude_returns_all(self, tmp_path: Path) -> None:
        """Empty include/exclude returns all routes."""
        routes = [_route(tmp_path, "users"), _route(tmp_path, "admin")]
        result = filter_routes(routes, base_path=tmp_path, include=[], exclude=[])
        assert result == routes

    def test_include_bare_name_matches_across_groups(self, tmp_path: Path) -> None:
        """Include bare name 'users' matches across groups."""
        routes = [
            _route(tmp_path, "(public)/users"),
            _route(tmp_path, "(admin)/users"),
            _route(tmp_path, "(admin)/settings"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=["users"], exclude=None)
        assert len(result) == 2
        assert routes[0] in result
        assert routes[1] in result

    def test_include_group_name_scopes_to_group(self, tmp_path: Path) -> None:
        """Include group name scopes filtering to that group."""
        routes = [
            _route(tmp_path, "(public)/users"),
            _route(tmp_path, "(public)/health"),
            _route(tmp_path, "(admin)/settings"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=["(public)"], exclude=None)
        assert len(result) == 2
        assert routes[0] in result
        assert routes[1] in result

    def test_include_glob_pattern(self, tmp_path: Path) -> None:
        """Include with glob pattern."""
        routes = [
            _route(tmp_path, "(public)/users"),
            _route(tmp_path, "(admin)/settings"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=["(public)/*"], exclude=None)
        assert len(result) == 1
        assert routes[0] in result

    def test_exclude_bare_name_matches_across_groups(self, tmp_path: Path) -> None:
        """Exclude bare name matches across groups."""
        routes = [
            _route(tmp_path, "(public)/users"),
            _route(tmp_path, "(admin)/users"),
            _route(tmp_path, "(admin)/settings"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=None, exclude=["users"])
        assert len(result) == 1
        assert routes[2] in result

    def test_exclude_group_name_scopes_to_group(self, tmp_path: Path) -> None:
        """Exclude group name scopes to that group."""
        routes = [
            _route(tmp_path, "(public)/users"),
            _route(tmp_path, "(admin)/settings"),
            _route(tmp_path, "health"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=None, exclude=["(admin)"])
        assert len(result) == 2
        assert routes[0] in result
        assert routes[2] in result

    def test_exclude_glob_pattern(self, tmp_path: Path) -> None:
        """Exclude with glob pattern."""
        routes = [
            _route(tmp_path, "(public)/users"),
            _route(tmp_path, "(admin)/settings"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=None, exclude=["(admin)/*"])
        assert len(result) == 1
        assert routes[0] in result

    def test_root_route_excluded_when_include_targets_specific_name(self, tmp_path: Path) -> None:
        """Root route excluded when include targets specific name."""
        routes = [
            _route(tmp_path, "."),
            _route(tmp_path, "users"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=["users"], exclude=None)
        assert len(result) == 1
        assert routes[1] in result

    def test_root_route_included_by_glob_star(self, tmp_path: Path) -> None:
        """Root route included by '*' glob pattern."""
        routes = [
            _route(tmp_path, "."),
            _route(tmp_path, "users"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=["*"], exclude=None)
        assert len(result) == 2

    def test_multiple_patterns_work_as_union(self, tmp_path: Path) -> None:
        """Multiple patterns work as union (OR)."""
        routes = [
            _route(tmp_path, "users"),
            _route(tmp_path, "admin"),
            _route(tmp_path, "health"),
        ]
        result = filter_routes(
            routes, base_path=tmp_path, include=["users", "health"], exclude=None
        )
        assert len(result) == 2
        assert routes[0] in result
        assert routes[2] in result

    def test_both_include_and_exclude_raises_error(self, tmp_path: Path) -> None:
        """Both include and exclude raises RouteFilterError."""
        routes = [_route(tmp_path, "users")]
        with pytest.raises(RouteFilterError):
            filter_routes(routes, base_path=tmp_path, include=["users"], exclude=["admin"])

    def test_include_bare_name_matches_descendants(self, tmp_path: Path) -> None:
        """Include bare name matches descendants."""
        routes = [
            _route(tmp_path, "users"),
            _route(tmp_path, "users/[id]"),
            _route(tmp_path, "health"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=["users"], exclude=None)
        assert len(result) == 2
        assert routes[0] in result
        assert routes[1] in result

    def test_exclude_bare_name_matches_descendants(self, tmp_path: Path) -> None:
        """Exclude bare name matches descendants."""
        routes = [
            _route(tmp_path, "users"),
            _route(tmp_path, "users/[id]"),
            _route(tmp_path, "health"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=None, exclude=["users"])
        assert len(result) == 1
        assert routes[2] in result

    def test_deeply_nested_segment_match(self, tmp_path: Path) -> None:
        """Bare name matches deeply nested path."""
        routes = [
            _route(tmp_path, "api/v1/(public)/users"),
            _route(tmp_path, "api/v1/(admin)/settings"),
        ]
        result = filter_routes(routes, base_path=tmp_path, include=["users"], exclude=None)
        assert len(result) == 1
        assert routes[0] in result


# ---------------------------------------------------------------------------
# compute_active_directories
# ---------------------------------------------------------------------------


class TestComputeActiveDirectories:
    """Tests for compute_active_directories()."""

    def test_empty_routes_returns_empty_set(self, tmp_path: Path) -> None:
        """Empty routes returns empty set."""
        result = compute_active_directories([], tmp_path)
        assert result == set()

    def test_single_root_route(self, tmp_path: Path) -> None:
        """Single root route includes base directory."""
        routes = [_route(tmp_path, ".")]
        result = compute_active_directories(routes, tmp_path)
        assert result == {tmp_path}

    def test_nested_route_includes_all_ancestors(self, tmp_path: Path) -> None:
        """Nested route includes base and all intermediate directories."""
        routes = [_route(tmp_path, "api/users")]
        result = compute_active_directories(routes, tmp_path)
        assert result == {tmp_path, tmp_path / "api", tmp_path / "api" / "users"}

    def test_multiple_routes_union_all_ancestor_chains(self, tmp_path: Path) -> None:
        """Multiple routes produce union of all ancestor chains."""
        routes = [
            _route(tmp_path, "api/users"),
            _route(tmp_path, "health"),
        ]
        result = compute_active_directories(routes, tmp_path)
        assert result == {
            tmp_path,
            tmp_path / "api",
            tmp_path / "api" / "users",
            tmp_path / "health",
        }


# ---------------------------------------------------------------------------
# filter_middleware_files
# ---------------------------------------------------------------------------


class TestFilterMiddlewareFiles:
    """Tests for filter_middleware_files()."""

    def test_empty_list_returns_empty(self, tmp_path: Path) -> None:
        """Empty middleware list returns empty list."""
        result = filter_middleware_files([], set())
        assert result == []

    def test_all_in_active_dirs_kept(self, tmp_path: Path) -> None:
        """Middleware in active directories are kept."""
        mw_files = [
            _mw_file(tmp_path, ".", 0),
            _mw_file(tmp_path, "api", 1),
        ]
        active = {tmp_path, tmp_path / "api"}
        result = filter_middleware_files(mw_files, active)
        assert result == mw_files

    def test_filters_out_inactive_dirs(self, tmp_path: Path) -> None:
        """Middleware in inactive directories are filtered out."""
        mw_files = [
            _mw_file(tmp_path, ".", 0),
            _mw_file(tmp_path, "api", 1),
            _mw_file(tmp_path, "(admin)", 1),
        ]
        active = {tmp_path, tmp_path / "api"}
        result = filter_middleware_files(mw_files, active)
        assert len(result) == 2
        assert mw_files[0] in result
        assert mw_files[1] in result
        assert mw_files[2] not in result
