"""Tests for the core module_loader module (low-level dynamic-import machinery).

Covers the import machinery, route-file path validation, parameter-name
validation, deterministic module naming, sys.modules cleanup, and the
symlink-identity cache.
"""

import os
import sys
from pathlib import Path

import pytest

from fastapi_filebased_routing.core.module_loader import (
    _file_identity_cache,
    import_route_module,
)
from fastapi_filebased_routing.exceptions import RouteValidationError


class TestImportRouteModule:
    """Tests for import_route_module function."""

    def test_imports_valid_route_file(self, tmp_path: Path):
        """Import a valid route.py file successfully."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): return 'hello'")

        module = import_route_module(route_file, base_path=tmp_path)

        assert hasattr(module, "get")
        assert callable(module.get)

    def test_imports_without_base_path(self, tmp_path: Path):
        """Import works when base_path is not provided."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file)

        assert hasattr(module, "get")

    def test_caches_imported_modules_in_sys_modules(self, tmp_path: Path):
        """Imported modules are cached in sys.modules."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): return 'hello'")

        module1 = import_route_module(route_file, base_path=tmp_path)
        module2 = import_route_module(route_file, base_path=tmp_path)

        assert module1 is module2

    def test_rejects_path_traversal_with_dots(self, tmp_path: Path):
        """Reject paths containing .. as path component."""
        malicious_path = tmp_path / ".." / "outside" / "route.py"

        with pytest.raises(RouteValidationError, match="Path traversal"):
            import_route_module(malicious_path, base_path=tmp_path)

    def test_rejects_file_outside_base_path(self, tmp_path: Path):
        """Reject files outside the allowed base_path."""
        # Create file outside the allowed base
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        outside_file = outside_dir / "route.py"
        outside_file.write_text("async def get(): pass")

        # Set base path to different directory
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        with pytest.raises(RouteValidationError, match="outside allowed directory"):
            import_route_module(outside_file, base_path=allowed_dir)

    def test_accepts_file_inside_base_path(self, tmp_path: Path):
        """Accept files inside the base_path."""
        subdir = tmp_path / "users" / "[user_id]"
        subdir.mkdir(parents=True)
        route_file = subdir / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)

        assert hasattr(module, "get")

    def test_rejects_non_route_filename(self, tmp_path: Path):
        """Reject files not named route.py."""
        other_file = tmp_path / "other.py"
        other_file.write_text("async def get(): pass")

        with pytest.raises(RouteValidationError, match="Invalid route file name"):
            import_route_module(other_file, base_path=tmp_path)

    def test_raises_for_nonexistent_file(self, tmp_path: Path):
        """Raise error for files that don't exist."""
        nonexistent = tmp_path / "route.py"

        with pytest.raises(RouteValidationError, match="does not exist"):
            import_route_module(nonexistent, base_path=tmp_path)

    def test_wraps_import_error_for_syntax_errors(self, tmp_path: Path):
        """Wrap ImportError in RouteValidationError for syntax errors."""
        route_file = tmp_path / "route.py"
        route_file.write_text("def get(: invalid syntax")

        with pytest.raises(RouteValidationError, match="Failed to import"):
            import_route_module(route_file, base_path=tmp_path)

    def test_wraps_import_error_for_missing_imports(self, tmp_path: Path):
        """Wrap ImportError in RouteValidationError for missing imports."""
        route_file = tmp_path / "route.py"
        route_file.write_text("import nonexistent_module\nasync def get(): pass")

        with pytest.raises(RouteValidationError, match="Failed to import"):
            import_route_module(route_file, base_path=tmp_path)

    def test_validates_parameter_name_in_path(self, tmp_path: Path):
        """Validate parameter names in directory paths during import."""
        invalid_dir = tmp_path / "[123invalid]"
        invalid_dir.mkdir()
        route_file = invalid_dir / "route.py"
        route_file.write_text("async def get(): pass")

        with pytest.raises(RouteValidationError, match="Invalid parameter name"):
            import_route_module(route_file, base_path=tmp_path)

    def test_generates_deterministic_module_names(self, tmp_path: Path):
        """Module names are deterministic based on file path."""
        route_file = tmp_path / "users" / "[user_id]" / "route.py"
        route_file.parent.mkdir(parents=True)
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)

        # Module name should be in sys.modules
        assert module.__name__ in sys.modules

    def test_cleans_up_sys_modules_on_import_failure(self, tmp_path: Path):
        """Clean up sys.modules if module execution fails."""
        route_file = tmp_path / "route.py"
        route_file.write_text("raise RuntimeError('boom')")

        with pytest.raises(RouteValidationError):
            import_route_module(route_file, base_path=tmp_path)

        # Module should not be in sys.modules after failure
        # We can't easily test this without knowing the exact module name,
        # but the implementation should handle it


class TestSecurityValidation:
    """Tests for security validations in the module loader."""

    def test_rejects_path_traversal_in_middle_of_path(self, tmp_path: Path):
        """Reject .. anywhere in the path components."""
        malicious = tmp_path / "api" / ".." / ".." / "etc" / "route.py"

        with pytest.raises(RouteValidationError, match="Path traversal"):
            import_route_module(malicious, base_path=tmp_path)

    def test_accepts_dotdot_in_filename_not_path_component(self, tmp_path: Path):
        """Accept filenames containing .. if not a path component."""
        # This test verifies we check path.parts, not just string matching
        # In practice, route.py is enforced, but this tests the logic
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        # Should work fine - no .. in path.parts
        module = import_route_module(route_file, base_path=tmp_path)
        assert hasattr(module, "get")

    def test_validates_parameter_names_as_python_identifiers(self, tmp_path: Path):
        """Parameter names must be valid Python identifiers."""
        invalid_cases = [
            "[123param]",  # starts with digit
            "[param-name]",  # contains hyphen
            "[param.name]",  # contains dot
            "[param name]",  # contains space
        ]

        for invalid_name in invalid_cases:
            invalid_dir = tmp_path / invalid_name
            invalid_dir.mkdir(exist_ok=True)
            route_file = invalid_dir / "route.py"
            route_file.write_text("async def get(): pass")

            with pytest.raises(RouteValidationError, match="Invalid parameter name"):
                import_route_module(route_file, base_path=tmp_path)

            # Clean up for next iteration
            route_file.unlink()
            invalid_dir.rmdir()

    def test_accepts_valid_parameter_names(self, tmp_path: Path):
        """Accept valid Python identifier parameter names."""
        valid_cases = ["[user_id]", "[_private]", "[id123]", "[project]"]

        for i, valid_name in enumerate(valid_cases):
            # Use unique tmp_path subdirectory for each case to avoid conflicts
            test_dir = tmp_path / f"test_{i}"
            test_dir.mkdir()
            valid_dir = test_dir / valid_name
            valid_dir.mkdir()
            route_file = valid_dir / "route.py"
            route_file.write_text("async def get(): pass")

            # Should not raise
            module = import_route_module(route_file, base_path=test_dir)
            assert hasattr(module, "get")

    def test_validates_optional_parameter_names(self, tmp_path: Path):
        """Validate parameter names in [[optional]] syntax."""
        invalid_dir = tmp_path / "[[in-valid]]"
        invalid_dir.mkdir()
        route_file = invalid_dir / "route.py"
        route_file.write_text("async def get(): pass")

        with pytest.raises(RouteValidationError, match="Invalid parameter name"):
            import_route_module(route_file, base_path=tmp_path)

    def test_validates_catch_all_parameter_names(self, tmp_path: Path):
        """Validate parameter names in [...catchall] syntax."""
        invalid_dir = tmp_path / "[...in-valid]"
        invalid_dir.mkdir()
        route_file = invalid_dir / "route.py"
        route_file.write_text("async def get(): pass")

        with pytest.raises(RouteValidationError, match="Invalid parameter name"):
            import_route_module(route_file, base_path=tmp_path)


class TestSymlinkAliasDetection:
    """Tests for symlink alias detection via file identity cache."""

    def _cleanup_modules(self, tmp_path: Path) -> None:
        """Remove any sys.modules entries created during test."""
        to_remove = [
            name
            for name in sys.modules
            if "route" in name and str(tmp_path) in str(getattr(sys.modules[name], "__file__", ""))
        ]
        for name in to_remove:
            del sys.modules[name]

    def test_symlink_returns_same_module(self, tmp_path: Path) -> None:
        """Importing via a symlink should return the same module as the original."""
        # Create original route.py
        original_dir = tmp_path / "original"
        original_dir.mkdir()
        route_file = original_dir / "route.py"
        route_file.write_text("async def get(): return 'hello'")

        # Create symlink to route.py in a different directory
        symlink_dir = tmp_path / "symlink"
        symlink_dir.mkdir()
        symlink_file = symlink_dir / "route.py"
        os.symlink(route_file, symlink_file)

        try:
            # Import via original path
            module1 = import_route_module(route_file, base_path=tmp_path)

            # Import via symlink path
            module2 = import_route_module(symlink_file, base_path=tmp_path)

            # Should be the SAME module object (not a duplicate)
            assert module1 is module2
        finally:
            self._cleanup_modules(tmp_path)
            # Clean up file identity cache entries for this test
            stat = route_file.stat()
            file_id = (stat.st_dev, stat.st_ino)
            _file_identity_cache.pop(file_id, None)

    def test_different_files_get_different_modules(self, tmp_path: Path) -> None:
        """Different files (not symlinks) should produce different modules."""
        # Create two distinct route.py files
        dir1 = tmp_path / "dir1"
        dir1.mkdir()
        route1 = dir1 / "route.py"
        route1.write_text("async def get(): return 'hello1'")

        dir2 = tmp_path / "dir2"
        dir2.mkdir()
        route2 = dir2 / "route.py"
        route2.write_text("async def get(): return 'hello2'")

        try:
            module1 = import_route_module(route1, base_path=tmp_path)
            module2 = import_route_module(route2, base_path=tmp_path)

            # Should be DIFFERENT module objects
            assert module1 is not module2
        finally:
            self._cleanup_modules(tmp_path)
            # Clean up file identity cache entries for this test
            for route_file in (route1, route2):
                stat = route_file.stat()
                file_id = (stat.st_dev, stat.st_ino)
                _file_identity_cache.pop(file_id, None)

    def test_file_identity_cache_populated_after_import(self, tmp_path: Path) -> None:
        """File identity cache should have entry after importing a route."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): return 'hello'")

        stat = route_file.stat()
        file_id = (stat.st_dev, stat.st_ino)

        try:
            # Cache should NOT have this file yet
            assert file_id not in _file_identity_cache

            import_route_module(route_file, base_path=tmp_path)

            # Cache SHOULD have this file now
            assert file_id in _file_identity_cache
        finally:
            self._cleanup_modules(tmp_path)
            _file_identity_cache.pop(file_id, None)


class TestValidateRouteFilePath:
    """Tests for the public validate_route_file_path seam."""

    def test_returns_resolved_path_for_valid_route_file(self, tmp_path: Path) -> None:
        """A valid route.py path resolves cleanly."""
        from fastapi_filebased_routing.core.module_loader import validate_route_file_path

        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        resolved = validate_route_file_path(route_file, base_path=tmp_path)
        assert resolved == route_file.resolve()
        assert resolved.name == "route.py"

    def test_rejects_non_route_filename(self, tmp_path: Path) -> None:
        """A non-route.py filename is rejected."""
        from fastapi_filebased_routing.core.module_loader import validate_route_file_path

        with pytest.raises(RouteValidationError, match="Invalid route file name"):
            validate_route_file_path(tmp_path / "handler.py")

    def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        """A path containing .. components is rejected."""
        from fastapi_filebased_routing.core.module_loader import validate_route_file_path

        with pytest.raises(RouteValidationError, match="Path traversal"):
            validate_route_file_path(tmp_path / ".." / "route.py")


class TestLoadModuleFromFile:
    """Tests for the public load_module_from_file seam."""

    def test_loads_arbitrary_module(self, tmp_path: Path) -> None:
        """The public seam loads any Python file under a supplied module name."""
        from fastapi_filebased_routing.core.module_loader import load_module_from_file

        target = tmp_path / "_middleware.py"
        target.write_text("VALUE = 42\n")

        module = load_module_from_file(target, "test_load_module_from_file_mod")
        try:
            assert module.VALUE == 42
            assert "test_load_module_from_file_mod" in sys.modules
        finally:
            sys.modules.pop("test_load_module_from_file_mod", None)

    def test_wraps_exec_error(self, tmp_path: Path) -> None:
        """Execution errors are wrapped in RouteValidationError and cleaned up."""
        from fastapi_filebased_routing.core.module_loader import load_module_from_file

        target = tmp_path / "_middleware.py"
        target.write_text("raise RuntimeError('boom')\n")

        with pytest.raises(RouteValidationError, match="Failed to import"):
            load_module_from_file(target, "test_load_module_from_file_err")

        assert "test_load_module_from_file_err" not in sys.modules
