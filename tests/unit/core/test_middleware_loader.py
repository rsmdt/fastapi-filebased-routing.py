"""Tests for the core middleware_loader module.

Covers loading directory ``_middleware.py`` files into a {directory: tuple}
map and collecting the parent-before-child cascade for a route directory.
"""

from pathlib import Path

import pytest

from fastapi_filebased_routing.core.discovery import DirectoryMiddleware
from fastapi_filebased_routing.core.middleware_loader import (
    collect_directory_middleware,
    load_directory_middleware,
)
from fastapi_filebased_routing.exceptions import MiddlewareValidationError


class TestLoadDirectoryMiddleware:
    """Test load_directory_middleware() helper function."""

    def test_loads_middleware_from_list(self, tmp_path: Path):
        """Loads middleware from _middleware.py with middleware = [fn1, fn2] list."""
        # Create _middleware.py with a list of functions
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
async def mw1(request, call_next):
    response = await call_next(request)
    return response

async def mw2(request, call_next):
    response = await call_next(request)
    return response

middleware = [mw1, mw2]
""")

        directory_middleware = [
            DirectoryMiddleware(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = load_directory_middleware(directory_middleware, tmp_path)

        assert mw_dir in result
        assert len(result[mw_dir]) == 2
        assert callable(result[mw_dir][0])
        assert callable(result[mw_dir][1])

    def test_handles_single_callable(self, tmp_path: Path):
        """Handles middleware = single_fn (single callable)."""
        # Create _middleware.py with a single callable
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
async def auth_middleware(request, call_next):
    response = await call_next(request)
    return response

middleware = auth_middleware
""")

        directory_middleware = [
            DirectoryMiddleware(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = load_directory_middleware(directory_middleware, tmp_path)

        assert mw_dir in result
        assert len(result[mw_dir]) == 1
        assert callable(result[mw_dir][0])

    def test_handles_inline_function(self, tmp_path: Path):
        """Handles inline async def middleware(request, call_next) function."""
        # Create _middleware.py with inline function definition
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
async def middleware(request, call_next):
    response = await call_next(request)
    return response
""")

        directory_middleware = [
            DirectoryMiddleware(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = load_directory_middleware(directory_middleware, tmp_path)

        assert mw_dir in result
        assert len(result[mw_dir]) == 1
        assert callable(result[mw_dir][0])

    def test_raises_error_when_import_fails(self, tmp_path: Path):
        """Raises MiddlewareValidationError when _middleware.py fails to import."""
        # Create _middleware.py with syntax error
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
async def middleware(request, call_next):
    # Syntax error
    return await call_next(request
""")

        directory_middleware = [
            DirectoryMiddleware(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        with pytest.raises(MiddlewareValidationError) as exc_info:
            load_directory_middleware(directory_middleware, tmp_path)

        assert "Failed to import" in str(exc_info.value)

    def test_raises_error_for_non_callable_middleware(self, tmp_path: Path):
        """Raises MiddlewareValidationError when middleware contains non-callable."""
        # Create _middleware.py with non-callable in list
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
middleware = ["not_a_function"]
""")

        directory_middleware = [
            DirectoryMiddleware(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        with pytest.raises(MiddlewareValidationError) as exc_info:
            load_directory_middleware(directory_middleware, tmp_path)

        assert "Non-callable middleware" in str(exc_info.value)

    def test_raises_error_for_sync_middleware(self, tmp_path: Path):
        """Raises MiddlewareValidationError for sync middleware."""
        # Create _middleware.py with sync function
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
def sync_middleware(request, call_next):
    return call_next(request)

middleware = sync_middleware
""")

        directory_middleware = [
            DirectoryMiddleware(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        with pytest.raises(MiddlewareValidationError) as exc_info:
            load_directory_middleware(directory_middleware, tmp_path)

        assert "must be async" in str(exc_info.value)

    def test_returns_empty_dict_for_empty_list(self, tmp_path: Path):
        """Returns empty dict for empty list."""
        # Create _middleware.py with empty list
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
middleware = []
""")

        directory_middleware = [
            DirectoryMiddleware(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = load_directory_middleware(directory_middleware, tmp_path)

        # Empty list means no middleware for that directory
        assert mw_dir in result
        assert len(result[mw_dir]) == 0

    def test_handles_multiple_directory_middleware_files(self, tmp_path: Path):
        """Handles multiple directory middleware files."""
        # Create first _middleware.py
        mw_dir1 = tmp_path / "api"
        mw_dir1.mkdir()
        mw_file1 = mw_dir1 / "_middleware.py"
        mw_file1.write_text("""
async def mw1(request, call_next):
    response = await call_next(request)
    return response

middleware = mw1
""")

        # Create second _middleware.py
        mw_dir2 = tmp_path / "api" / "v1"
        mw_dir2.mkdir()
        mw_file2 = mw_dir2 / "_middleware.py"
        mw_file2.write_text("""
async def mw2(request, call_next):
    response = await call_next(request)
    return response

middleware = mw2
""")

        directory_middleware = [
            DirectoryMiddleware(file_path=mw_file1, directory=mw_dir1, depth=1),
            DirectoryMiddleware(file_path=mw_file2, directory=mw_dir2, depth=2),
        ]

        result = load_directory_middleware(directory_middleware, tmp_path)

        assert len(result) == 2
        assert mw_dir1 in result
        assert mw_dir2 in result
        assert len(result[mw_dir1]) == 1
        assert len(result[mw_dir2]) == 1


class TestCollectDirectoryMiddleware:
    """Test collect_directory_middleware() helper function."""

    def test_collects_from_base_to_route_dir(self, tmp_path: Path):
        """Collects middleware from base to route dir."""

        # Create mock middleware for base and subdirectory
        async def base_mw(request, call_next):
            return await call_next(request)

        async def sub_mw(request, call_next):
            return await call_next(request)

        # Setup directory structure
        sub_dir = tmp_path / "api" / "users"
        sub_dir.mkdir(parents=True)

        dir_middleware = {
            tmp_path: (base_mw,),
            tmp_path / "api": (sub_mw,),
        }

        result = collect_directory_middleware(
            route_dir=sub_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        assert len(result) == 2
        assert result[0] == base_mw
        assert result[1] == sub_mw

    def test_sibling_directory_middleware_does_not_apply(self, tmp_path: Path):
        """Sibling directory middleware does NOT apply."""

        async def sibling_mw(request, call_next):
            return await call_next(request)

        # Create sibling directories
        route_dir = tmp_path / "api" / "users"
        route_dir.mkdir(parents=True)

        sibling_dir = tmp_path / "api" / "posts"
        sibling_dir.mkdir(parents=True)

        dir_middleware = {
            sibling_dir: (sibling_mw,),
        }

        result = collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        # No middleware should be collected from sibling
        assert len(result) == 0

    def test_route_group_middleware_applies_within_group(self, tmp_path: Path):
        """Route group (name)/ middleware applies within group."""

        async def group_mw(request, call_next):
            return await call_next(request)

        # Create route group directory
        group_dir = tmp_path / "(admin)"
        group_dir.mkdir()

        route_dir = tmp_path / "(admin)" / "users"
        route_dir.mkdir()

        dir_middleware = {
            group_dir: (group_mw,),
        }

        result = collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        assert len(result) == 1
        assert result[0] == group_mw

    def test_no_directory_middleware_returns_empty_tuple(self, tmp_path: Path):
        """No directory middleware returns empty tuple."""
        route_dir = tmp_path / "api" / "users"
        route_dir.mkdir(parents=True)

        result = collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware={},
        )

        assert result == ()

    def test_multiple_levels_ordered_correctly(self, tmp_path: Path):
        """Multiple levels ordered correctly (parent before child)."""

        async def base_mw(request, call_next):
            return await call_next(request)

        async def api_mw(request, call_next):
            return await call_next(request)

        async def v1_mw(request, call_next):
            return await call_next(request)

        async def users_mw(request, call_next):
            return await call_next(request)

        # Setup deeply nested directory structure
        route_dir = tmp_path / "api" / "v1" / "users"
        route_dir.mkdir(parents=True)

        dir_middleware = {
            tmp_path: (base_mw,),
            tmp_path / "api": (api_mw,),
            tmp_path / "api" / "v1": (v1_mw,),
            route_dir: (users_mw,),
        }

        result = collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        # Should be ordered from parent to child
        assert len(result) == 4
        assert result[0] == base_mw
        assert result[1] == api_mw
        assert result[2] == v1_mw
        assert result[3] == users_mw

    def test_only_collects_middleware_from_directories_that_have_it(self, tmp_path: Path):
        """Only collects middleware from directories that have it."""

        async def base_mw(request, call_next):
            return await call_next(request)

        async def users_mw(request, call_next):
            return await call_next(request)

        # Setup nested directory structure where middle level has no middleware
        route_dir = tmp_path / "api" / "v1" / "users"
        route_dir.mkdir(parents=True)

        dir_middleware = {
            tmp_path: (base_mw,),
            # No middleware for "api" or "v1"
            route_dir: (users_mw,),
        }

        result = collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        # Should only have base and users middleware
        assert len(result) == 2
        assert result[0] == base_mw
        assert result[1] == users_mw
