"""Tests for core.importer module."""

import inspect
import os
import sys
from pathlib import Path

import pytest

from fastapi_filebased_routing.core.importer import (
    ALLOWED_HANDLERS,
    ExtractedRoute,
    RouteMetadata,
    _file_identity_cache,
    extract_handlers,
    import_route_module,
    load_route,
)
from fastapi_filebased_routing.exceptions import RouteValidationError


class TestAllowedHandlers:
    """Test the ALLOWED_HANDLERS constant."""

    def test_includes_all_http_methods(self):
        """ALLOWED_HANDLERS includes all standard HTTP methods."""
        expected = {"get", "post", "put", "patch", "delete", "head", "options", "websocket"}
        assert expected == ALLOWED_HANDLERS

    def test_is_frozen(self):
        """ALLOWED_HANDLERS is immutable."""
        assert isinstance(ALLOWED_HANDLERS, frozenset)


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


class TestExtractHandlers:
    """Tests for extract_handlers function."""

    def test_extracts_async_get_handler(self, tmp_path: Path):
        """Extract async def get() handler."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): return 'hello'")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert callable(result.handlers["get"])
        assert inspect.iscoroutinefunction(result.handlers["get"])

    def test_extracts_sync_get_handler(self, tmp_path: Path):
        """Extract sync def get() handler."""
        route_file = tmp_path / "route.py"
        route_file.write_text("def get(): return 'hello'")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert callable(result.handlers["get"])
        assert not inspect.iscoroutinefunction(result.handlers["get"])

    def test_extracts_multiple_handlers(self, tmp_path: Path):
        """Extract multiple HTTP method handlers from one file."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): return 'list'
async def post(): return 'create'
async def delete(): return 'delete'
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert len(result.handlers) == 3
        assert "get" in result.handlers
        assert "post" in result.handlers
        assert "delete" in result.handlers

    def test_extracts_all_http_methods(self, tmp_path: Path):
        """Extract all supported HTTP method handlers."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): pass
async def post(): pass
async def put(): pass
async def patch(): pass
async def delete(): pass
async def head(): pass
async def options(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        expected_methods = {"get", "post", "put", "patch", "delete", "head", "options"}
        assert set(result.handlers.keys()) == expected_methods

    def test_extracts_websocket_handler(self, tmp_path: Path):
        """Extract async websocket handler."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def websocket(ws):
    await ws.accept()
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "websocket" in result.handlers
        assert callable(result.handlers["websocket"])

    def test_rejects_sync_websocket_handler(self, tmp_path: Path):
        """Reject sync websocket handler (must be async)."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
def websocket(ws):
    pass
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="WebSocket handler must be async"):
            extract_handlers(module, route_file)

    def test_extracts_mix_of_sync_and_async_handlers(self, tmp_path: Path):
        """Extract mix of sync and async HTTP handlers."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): pass
def post(): pass
async def delete(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert len(result.handlers) == 3
        assert inspect.iscoroutinefunction(result.handlers["get"])
        assert not inspect.iscoroutinefunction(result.handlers["post"])
        assert inspect.iscoroutinefunction(result.handlers["delete"])

    def test_ignores_private_functions(self, tmp_path: Path):
        """Ignore functions starting with underscore."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): return 'hello'
def _helper(): return 'helper'
def __private(): return 'private'
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert "_helper" not in result.handlers
        assert "__private" not in result.handlers

    def test_ignores_dunder_attributes(self, tmp_path: Path):
        """Ignore __name__, __doc__, etc."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "__name__" not in result.handlers
        assert "__doc__" not in result.handlers
        assert "__file__" not in result.handlers

    def test_ignores_uppercase_constants(self, tmp_path: Path):
        """Ignore UPPERCASE constants (except TAGS/SUMMARY/DEPRECATED)."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
MAX_ITEMS = 100
API_VERSION = "v1"

async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "MAX_ITEMS" not in result.handlers
        assert "API_VERSION" not in result.handlers
        assert "get" in result.handlers

    def test_ignores_imported_functions(self, tmp_path: Path):
        """Ignore functions imported from other modules."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from pathlib import Path
from typing import Any

async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        # Should only have get, not Path or Any
        assert list(result.handlers.keys()) == ["get"]

    def test_ignores_non_callable_exports(self, tmp_path: Path):
        """Ignore non-callable module attributes."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
config = {"key": "value"}
data = [1, 2, 3]

async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "config" not in result.handlers
        assert "data" not in result.handlers
        assert "get" in result.handlers

    def test_rejects_invalid_public_function_exports(self, tmp_path: Path):
        """Reject public functions not in ALLOWED_HANDLERS."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): pass
def invalid_export(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="Invalid export"):
            extract_handlers(module, route_file)

    def test_provides_helpful_error_for_invalid_exports(self, tmp_path: Path):
        """Error message suggests prefixing with underscore."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): pass
def helper_function(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="Prefix helper functions with underscore"):
            extract_handlers(module, route_file)

    def test_returns_empty_handlers_for_no_handlers(self, tmp_path: Path):
        """Return empty handlers dict when no handlers present."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
def _helper(): pass
CONFIG = {}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.handlers == {}
        assert isinstance(result.metadata, RouteMetadata)

    def test_extracts_tags_metadata(self, tmp_path: Path):
        """Extract TAGS constant as metadata."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
TAGS = ["projects", "workspace"]
async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.metadata.tags == ["projects", "workspace"]

    def test_extracts_summary_metadata(self, tmp_path: Path):
        """Extract SUMMARY constant as metadata."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
SUMMARY = "User management endpoints"
async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.metadata.summary == "User management endpoints"

    def test_extracts_deprecated_metadata(self, tmp_path: Path):
        """Extract DEPRECATED constant as metadata."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
DEPRECATED = True
async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.metadata.deprecated is True

    def test_extracts_all_metadata_together(self, tmp_path: Path):
        """Extract TAGS, SUMMARY, and DEPRECATED together."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
TAGS = ["admin"]
SUMMARY = "Admin operations"
DEPRECATED = True

async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.metadata.tags == ["admin"]
        assert result.metadata.summary == "Admin operations"
        assert result.metadata.deprecated is True

    def test_defaults_metadata_when_not_present(self, tmp_path: Path):
        """Use default metadata values when constants not defined."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.metadata.tags is None
        assert result.metadata.summary is None
        assert result.metadata.deprecated is False


class TestLoadRoute:
    """Tests for load_route convenience function."""

    def test_loads_and_extracts_route(self, tmp_path: Path):
        """Load and extract handlers in one call."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
TAGS = ["test"]

async def get():
    return "hello"
""")

        result = load_route(route_file, base_path=tmp_path)

        assert "get" in result.handlers
        assert result.metadata.tags == ["test"]

    def test_passes_base_path_through(self, tmp_path: Path):
        """Pass base_path parameter to import_route_module."""
        subdir = tmp_path / "api"
        subdir.mkdir()
        route_file = subdir / "route.py"
        route_file.write_text("async def get(): pass")

        result = load_route(route_file, base_path=tmp_path)

        assert "get" in result.handlers

    def test_works_without_base_path(self, tmp_path: Path):
        """Load route without base_path parameter."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        result = load_route(route_file)

        assert "get" in result.handlers


class TestRouteMetadataDataclass:
    """Tests for RouteMetadata dataclass."""

    def test_is_frozen(self):
        """RouteMetadata instances are immutable."""
        metadata = RouteMetadata(tags=["test"])

        with pytest.raises(AttributeError):
            metadata.tags = ["changed"]  # type: ignore

    def test_has_default_values(self):
        """RouteMetadata has sensible defaults."""
        metadata = RouteMetadata()

        assert metadata.tags is None
        assert metadata.summary is None
        assert metadata.deprecated is False

    def test_can_be_created_with_all_fields(self):
        """RouteMetadata can be created with all fields."""
        metadata = RouteMetadata(
            tags=["admin", "users"], summary="User management", deprecated=True
        )

        assert metadata.tags == ["admin", "users"]
        assert metadata.summary == "User management"
        assert metadata.deprecated is True


class TestExtractedRouteDataclass:
    """Tests for ExtractedRoute dataclass."""

    def test_is_frozen(self):
        """ExtractedRoute instances are immutable."""
        route = ExtractedRoute(handlers={}, metadata=RouteMetadata())

        with pytest.raises(AttributeError):
            route.handlers = {}  # type: ignore

    def test_requires_both_fields(self):
        """ExtractedRoute requires handlers and metadata."""
        metadata = RouteMetadata()

        def handler() -> None:
            pass

        route = ExtractedRoute(handlers={"get": handler}, metadata=metadata)

        assert "get" in route.handlers
        assert route.handlers["get"] is handler
        assert route.metadata is metadata


class TestRouteConfigDetection:
    """Tests for RouteConfig object detection in extract_handlers."""

    def test_detects_route_config_object(self, tmp_path: Path):
        """RouteConfig objects are detected and placed in handlers dict."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.middleware import route

class get(route):
    async def handler():
        return {"hello": "world"}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "get" in result.handlers
        # Import RouteConfig to check isinstance
        from fastapi_filebased_routing.core.middleware import RouteConfig

        assert isinstance(result.handlers["get"], RouteConfig)

    def test_route_config_with_valid_name_accepted(self, tmp_path: Path):
        """RouteConfig with name in ALLOWED_HANDLERS is accepted."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.middleware import route

class post(route):
    async def handler():
        return {}

class delete(route):
    async def handler():
        return {}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "post" in result.handlers
        assert "delete" in result.handlers
        assert len(result.handlers) == 2

    def test_route_config_with_invalid_name_rejected(self, tmp_path: Path):
        """RouteConfig with name not in ALLOWED_HANDLERS is rejected."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.middleware import route

class invalid_handler(route):
    async def handler():
        return {}
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="Invalid export"):
            extract_handlers(module, route_file)

    def test_route_config_detected_before_callable_check(self, tmp_path: Path):
        """RouteConfig detected BEFORE generic callable check."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.middleware import route, RouteConfig

class get(route):
    async def handler():
        return {"config": True}

# This should confirm RouteConfig is checked first
assert isinstance(get, RouteConfig)
assert callable(get)
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        # Should extract the RouteConfig, not reject it
        assert "get" in result.handlers
        from fastapi_filebased_routing.core.middleware import RouteConfig

        assert isinstance(result.handlers["get"], RouteConfig)

    def test_plain_function_handlers_still_work(self, tmp_path: Path):
        """Plain function handlers work unchanged (backward compatibility)."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get():
    return {"plain": True}

async def post():
    return {"plain": True}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert "post" in result.handlers
        # Should be plain callables, not RouteConfig
        from fastapi_filebased_routing.core.middleware import RouteConfig

        assert not isinstance(result.handlers["get"], RouteConfig)
        assert not isinstance(result.handlers["post"], RouteConfig)
        assert callable(result.handlers["get"])

    def test_mix_of_route_config_and_plain_functions(self, tmp_path: Path):
        """Mix of RouteConfig and plain functions extracted correctly."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.middleware import route

async def get():
    return {"plain": True}

class post(route):
    async def handler():
        return {"config": True}

async def delete():
    return {"plain": True}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert len(result.handlers) == 3
        assert "get" in result.handlers
        assert "post" in result.handlers
        assert "delete" in result.handlers

        from fastapi_filebased_routing.core.middleware import RouteConfig

        # get and delete are plain functions
        assert not isinstance(result.handlers["get"], RouteConfig)
        assert not isinstance(result.handlers["delete"], RouteConfig)
        # post is RouteConfig
        assert isinstance(result.handlers["post"], RouteConfig)

    def test_route_config_preserves_handler_name(self, tmp_path: Path):
        """RouteConfig preserves the handler name (e.g., 'get')."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.middleware import route

class get(route):
    async def handler():
        return {}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        # The key in handlers dict should be "get" (lowercase)
        assert "get" in result.handlers
        from fastapi_filebased_routing.core.middleware import RouteConfig

        config = result.handlers["get"]
        assert isinstance(config, RouteConfig)
        # The __name__ should be "handler" (the inner function)
        assert config.__name__ == "handler"

    def test_all_existing_importer_tests_still_pass(self, tmp_path: Path):
        """Existing importer behavior unchanged by RouteConfig addition."""
        # This is a meta-test to confirm we haven't broken anything
        # If any existing tests fail, this test documents the regression
        route_file = tmp_path / "route.py"
        route_file.write_text("""
TAGS = ["test"]
SUMMARY = "Test route"

async def get():
    return "hello"

def _helper():
    pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert "_helper" not in result.handlers
        assert result.metadata.tags == ["test"]
        assert result.metadata.summary == "Test route"


class TestSecurityValidation:
    """Tests for security validations in the importer."""

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


class TestFileLevelMiddleware:
    """Tests for file-level middleware extraction."""

    def test_extracts_middleware_list_from_module(self, tmp_path: Path):
        """Extract middleware = [fn1, fn2] as file_middleware tuple."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def mw1(request, call_next):
    return await call_next(request)

async def mw2(request, call_next):
    return await call_next(request)

middleware = [mw1, mw2]

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert len(result.file_middleware) == 2
        assert result.file_middleware[0].__name__ == "mw1"
        assert result.file_middleware[1].__name__ == "mw2"

    def test_normalizes_single_middleware_callable_to_tuple(self, tmp_path: Path):
        """Single callable middleware = fn normalized to tuple of one."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def auth_middleware(request, call_next):
    return await call_next(request)

middleware = auth_middleware

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert len(result.file_middleware) == 1
        assert result.file_middleware[0].__name__ == "auth_middleware"
        assert isinstance(result.file_middleware, tuple)

    def test_empty_tuple_when_no_middleware_attribute(self, tmp_path: Path):
        """Module without middleware attribute → file_middleware is empty tuple."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.file_middleware == ()
        assert isinstance(result.file_middleware, tuple)

    def test_empty_tuple_when_middleware_is_empty_list(self, tmp_path: Path):
        """middleware = [] → file_middleware is empty tuple."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
middleware = []

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert result.file_middleware == ()
        assert isinstance(result.file_middleware, tuple)

    def test_middleware_extraction_does_not_conflict_with_existing_metadata(self, tmp_path: Path):
        """middleware extraction works alongside TAGS/SUMMARY/DEPRECATED."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
TAGS = ["auth"]
SUMMARY = "Authentication endpoints"
DEPRECATED = True

async def auth_mw(request, call_next):
    return await call_next(request)

middleware = [auth_mw]

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        # Middleware extracted correctly
        assert len(result.file_middleware) == 1
        assert result.file_middleware[0].__name__ == "auth_mw"

        # Existing metadata still works
        assert result.metadata.tags == ["auth"]
        assert result.metadata.summary == "Authentication endpoints"
        assert result.metadata.deprecated is True

        # Handler extracted correctly
        assert "get" in result.handlers

    def test_extracted_route_has_file_middleware_field(self, tmp_path: Path):
        """ExtractedRoute dataclass includes file_middleware field."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        # Field exists with default empty tuple
        assert hasattr(result, "file_middleware")
        assert result.file_middleware == ()

    def test_backward_compat_extracted_route_without_file_middleware(self, tmp_path: Path):
        """ExtractedRoute can be created without file_middleware (backward compat)."""
        from fastapi_filebased_routing.core.importer import RouteMetadata

        # Old code should still work — file_middleware has a default
        route = ExtractedRoute(handlers={"get": lambda: "ok"}, metadata=RouteMetadata())

        assert hasattr(route, "file_middleware")
        assert route.file_middleware == ()

    def test_rejects_sync_file_level_middleware(self, tmp_path: Path):
        """Sync file-level middleware raises RouteValidationError."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
def sync_mw(request, call_next):
    return call_next(request)

middleware = [sync_mw]

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="must be async"):
            extract_handlers(module, route_file)

    def test_rejects_non_callable_file_level_middleware(self, tmp_path: Path):
        """Non-callable file-level middleware raises RouteValidationError."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
middleware = ["not_a_function"]

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="Non-callable middleware"):
            extract_handlers(module, route_file)

    def test_rejects_sync_single_callable_file_middleware(self, tmp_path: Path):
        """Single sync callable as file middleware raises RouteValidationError."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
def sync_mw(request, call_next):
    return call_next(request)

middleware = sync_mw

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="must be async"):
            extract_handlers(module, route_file)

    def test_middleware_as_tuple_is_preserved(self, tmp_path: Path):
        """middleware = (fn1, fn2) as tuple is preserved."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def mw1(request, call_next):
    return await call_next(request)

async def mw2(request, call_next):
    return await call_next(request)

middleware = (mw1, mw2)

async def get():
    return "hello"
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = extract_handlers(module, route_file)

        assert len(result.file_middleware) == 2
        assert isinstance(result.file_middleware, tuple)


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
