"""Tests for the core handlers module (high-level route.py interpretation).

Covers verb-handler extraction, RouteMetadata, invalid-export rules, the
async-websocket rule, file-level middleware, Route-subclass detection, and the
load_route public entry point.
"""

import inspect
from pathlib import Path

import pytest

from fastapi_filebased_routing.core.handlers import (
    ALLOWED_HANDLERS,
    ExtractedRoute,
    RouteMetadata,
    _extract_handlers,
    load_route,
)
from fastapi_filebased_routing.core.module_loader import import_route_module
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


class TestExtractHandlers:
    """Tests for _extract_handlers function."""

    def test_extracts_async_get_handler(self, tmp_path: Path):
        """Extract async def get() handler."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): return 'hello'")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert callable(result.handlers["get"])
        assert inspect.iscoroutinefunction(result.handlers["get"])

    def test_extracts_sync_get_handler(self, tmp_path: Path):
        """Extract sync def get() handler."""
        route_file = tmp_path / "route.py"
        route_file.write_text("def get(): return 'hello'")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
            _extract_handlers(module, route_file)

    def test_extracts_mix_of_sync_and_async_handlers(self, tmp_path: Path):
        """Extract mix of sync and async HTTP handlers."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): pass
def post(): pass
async def delete(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert "_helper" not in result.handlers
        assert "__private" not in result.handlers

    def test_ignores_dunder_attributes(self, tmp_path: Path):
        """Ignore __name__, __doc__, etc."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
            _extract_handlers(module, route_file)

    def test_provides_helpful_error_for_invalid_exports(self, tmp_path: Path):
        """Error message suggests prefixing with underscore."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
async def get(): pass
def helper_function(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="Prefix helper functions with underscore"):
            _extract_handlers(module, route_file)

    def test_returns_empty_handlers_for_no_handlers(self, tmp_path: Path):
        """Return empty handlers dict when no handlers present."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
def _helper(): pass
CONFIG = {}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

        assert result.metadata.tags == ["projects", "workspace"]

    def test_extracts_summary_metadata(self, tmp_path: Path):
        """Extract SUMMARY constant as metadata."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
SUMMARY = "User management endpoints"
async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        assert result.metadata.summary == "User management endpoints"

    def test_extracts_deprecated_metadata(self, tmp_path: Path):
        """Extract DEPRECATED constant as metadata."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
DEPRECATED = True
async def get(): pass
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

        assert result.metadata.tags == ["admin"]
        assert result.metadata.summary == "Admin operations"
        assert result.metadata.deprecated is True

    def test_defaults_metadata_when_not_present(self, tmp_path: Path):
        """Use default metadata values when constants not defined."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

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
        """Pass base_path parameter through to the module loader."""
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
    """Tests for RouteConfig object detection in _extract_handlers."""

    def test_detects_route_config_object(self, tmp_path: Path):
        """RouteConfig objects are detected and placed in handlers dict."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route

class GET(Route):
    async def handler():
        return {"hello": "world"}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        assert "get" in result.handlers
        # Import RouteConfig to check isinstance
        from fastapi_filebased_routing.core.routes import RouteConfig

        assert isinstance(result.handlers["get"], RouteConfig)

    def test_route_config_with_valid_name_accepted(self, tmp_path: Path):
        """RouteConfig with name in ALLOWED_HANDLERS is accepted."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route

class POST(Route):
    async def handler():
        return {}

class DELETE(Route):
    async def handler():
        return {}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        assert "post" in result.handlers
        assert "delete" in result.handlers
        assert len(result.handlers) == 2

    def test_route_config_with_invalid_name_rejected(self, tmp_path: Path):
        """RouteConfig with name not in ALLOWED_HANDLERS is rejected."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route

class invalid_handler(Route):
    async def handler():
        return {}
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="Invalid export"):
            _extract_handlers(module, route_file)

    def test_route_subclass_detected_before_constant_skip(self, tmp_path: Path):
        """All-caps verb names are detected as Route subclasses, not skipped as constants."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route, RouteConfig

class GET(Route):
    async def handler():
        return {"config": True}

# GET stays a real class; its _config is a RouteConfig
assert isinstance(GET, type)
assert isinstance(GET._config, RouteConfig)
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        # "GET".isupper() is True, but it is detected as a Route subclass before
        # the uppercase-constant skip, and registered under its lowercased name.
        assert "get" in result.handlers
        from fastapi_filebased_routing.core.routes import RouteConfig

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
        result = _extract_handlers(module, route_file)

        assert "get" in result.handlers
        assert "post" in result.handlers
        # Should be plain callables, not RouteConfig
        from fastapi_filebased_routing.core.routes import RouteConfig

        assert not isinstance(result.handlers["get"], RouteConfig)
        assert not isinstance(result.handlers["post"], RouteConfig)
        assert callable(result.handlers["get"])

    def test_mix_of_route_config_and_plain_functions(self, tmp_path: Path):
        """Mix of RouteConfig and plain functions extracted correctly."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route

async def get():
    return {"plain": True}

class POST(Route):
    async def handler():
        return {"config": True}

async def delete():
    return {"plain": True}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        assert len(result.handlers) == 3
        assert "get" in result.handlers
        assert "post" in result.handlers
        assert "delete" in result.handlers

        from fastapi_filebased_routing.core.routes import RouteConfig

        # get and delete are plain functions
        assert not isinstance(result.handlers["get"], RouteConfig)
        assert not isinstance(result.handlers["delete"], RouteConfig)
        # post is RouteConfig
        assert isinstance(result.handlers["post"], RouteConfig)

    def test_route_config_preserves_handler_name(self, tmp_path: Path):
        """RouteConfig preserves the handler name (e.g., 'get')."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route

class GET(Route):
    async def handler():
        return {}
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        # The key in handlers dict should be "get" (lowercase)
        assert "get" in result.handlers
        from fastapi_filebased_routing.core.routes import RouteConfig

        config = result.handlers["get"]
        assert isinstance(config, RouteConfig)
        # The __name__ should be "handler" (the inner function)
        assert config.__name__ == "handler"

    def test_websocket_route_subclass_async_handler_accepted(self, tmp_path: Path):
        """class WEBSOCKET(Route): with an async handler is accepted."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route

class WEBSOCKET(Route):
    async def handler(ws):
        return None
""")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

        assert "websocket" in result.handlers

    def test_websocket_route_subclass_sync_handler_rejected(self, tmp_path: Path):
        """class WEBSOCKET(Route): with a sync handler raises RouteValidationError."""
        route_file = tmp_path / "route.py"
        route_file.write_text("""
from fastapi_filebased_routing.core.routes import Route

class WEBSOCKET(Route):
    @staticmethod
    def handler(ws):
        return None
""")

        module = import_route_module(route_file, base_path=tmp_path)

        with pytest.raises(RouteValidationError, match="WebSocket handler must be async"):
            _extract_handlers(module, route_file)


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
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

        assert len(result.file_middleware) == 1
        assert result.file_middleware[0].__name__ == "auth_middleware"
        assert isinstance(result.file_middleware, tuple)

    def test_empty_tuple_when_no_middleware_attribute(self, tmp_path: Path):
        """Module without middleware attribute → file_middleware is empty tuple."""
        route_file = tmp_path / "route.py"
        route_file.write_text("async def get(): pass")

        module = import_route_module(route_file, base_path=tmp_path)
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

        # Field exists with default empty tuple
        assert hasattr(result, "file_middleware")
        assert result.file_middleware == ()

    def test_backward_compat_extracted_route_without_file_middleware(self, tmp_path: Path):
        """ExtractedRoute can be created without file_middleware (backward compat)."""
        # file_middleware has a default — old construction still works
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
            _extract_handlers(module, route_file)

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
            _extract_handlers(module, route_file)

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
            _extract_handlers(module, route_file)

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
        result = _extract_handlers(module, route_file)

        assert len(result.file_middleware) == 2
        assert isinstance(result.file_middleware, tuple)
