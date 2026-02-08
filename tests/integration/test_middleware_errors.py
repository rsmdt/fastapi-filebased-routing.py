"""Integration tests for middleware error scenarios.

These tests verify that middleware validation errors are raised at STARTUP
(when create_router_from_path is called), not during request handling.
Each error scenario produces a descriptive, actionable error message.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from fastapi_filebased_routing import create_router_from_path
from fastapi_filebased_routing.exceptions import (
    MiddlewareValidationError,
    RouteValidationError,
)


class TestMiddlewareImportFailure:
    """_middleware.py import failures raise MiddlewareValidationError at startup."""

    def test_syntax_error_in_middleware_file_raises_at_startup(self, tmp_path: Path):
        """Syntax error in _middleware.py raises MiddlewareValidationError at startup."""
        # Create _middleware.py with syntax error
        mw_content = """
# Broken middleware file
middleware = [invalid syntax here
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route to prove the error is in middleware, not route
        route_content = """
async def get():
    return {"status": "ok"}
"""
        route_dir = tmp_path / "health"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(route_content)

        # Error should occur at startup
        with pytest.raises(MiddlewareValidationError, match="Failed to import"):
            create_router_from_path(tmp_path)

    def test_import_error_in_middleware_file_raises_at_startup(self, tmp_path: Path):
        """Missing import in _middleware.py raises MiddlewareValidationError at startup."""
        # Create _middleware.py that imports nonexistent module
        mw_content = """
import nonexistent_middleware_module

middleware = [nonexistent_middleware_module.auth]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route
        route_dir = tmp_path / "api"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        # Error should occur at startup
        with pytest.raises(MiddlewareValidationError, match="Failed to import"):
            create_router_from_path(tmp_path)

    def test_runtime_error_in_middleware_file_raises_at_startup(self, tmp_path: Path):
        """Runtime error during _middleware.py execution raises at startup."""
        # Create _middleware.py with runtime error
        mw_content = """
raise ValueError("Middleware initialization failed")

async def my_middleware(request, call_next):
    return await call_next(request)

middleware = [my_middleware]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        # Error should occur at startup and include original error message
        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "initialization failed" in error_message
        assert "_middleware.py" in error_message

    def test_middleware_import_error_includes_file_path(self, tmp_path: Path):
        """Error message includes the path to the offending _middleware.py."""
        # Create nested middleware file with syntax error
        api_dir = tmp_path / "api"
        api_dir.mkdir()

        mw_content = """
middleware = [broken
"""
        (api_dir / "_middleware.py").write_text(mw_content)

        # Create a route
        users_dir = api_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text("async def get(): return {}")

        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "_middleware.py" in error_message


class TestMiddlewareNonCallable:
    """Non-callable values in middleware list raise MiddlewareValidationError at startup."""

    def test_integer_in_middleware_list_raises_at_startup(self, tmp_path: Path):
        """middleware = [42] raises MiddlewareValidationError at startup."""
        # Create _middleware.py with non-callable
        mw_content = """
middleware = [42]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        # Error should occur at startup
        with pytest.raises(MiddlewareValidationError, match="Non-callable"):
            create_router_from_path(tmp_path)

    def test_string_in_middleware_list_raises_at_startup(self, tmp_path: Path):
        """middleware = ["auth"] raises MiddlewareValidationError at startup."""
        # Create _middleware.py with string instead of callable
        mw_content = """
middleware = ["should_be_function"]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route
        route_dir = tmp_path / "products"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def post(): return {}")

        with pytest.raises(MiddlewareValidationError, match="Non-callable"):
            create_router_from_path(tmp_path)

    def test_none_in_middleware_list_raises_at_startup(self, tmp_path: Path):
        """middleware = [None] raises MiddlewareValidationError at startup."""
        # Create _middleware.py with None
        mw_content = """
middleware = [None]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route
        route_dir = tmp_path / "admin"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        with pytest.raises(MiddlewareValidationError, match="Non-callable"):
            create_router_from_path(tmp_path)

    def test_mixed_valid_and_invalid_middleware_raises_at_startup(self, tmp_path: Path):
        """middleware = [valid_fn, 42] raises MiddlewareValidationError at startup."""
        # Create _middleware.py with mixed valid and invalid
        mw_content = """
async def valid_middleware(request, call_next):
    return await call_next(request)

middleware = [valid_middleware, 99]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route
        route_dir = tmp_path / "data"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        # Should fail on the non-callable at index 1
        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "Non-callable" in error_message
        assert "index 1" in error_message

    def test_non_callable_error_includes_index_and_file_path(self, tmp_path: Path):
        """Error message includes the index and file path for debugging."""
        # Create _middleware.py with non-callable at specific index
        mw_content = """
async def mw1(request, call_next):
    return await call_next(request)

async def mw2(request, call_next):
    return await call_next(request)

middleware = [mw1, mw2, "not_callable"]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a route
        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "index 2" in error_message
        assert "_middleware.py" in error_message


class TestMiddlewareSyncFunction:
    """Sync middleware functions raise MiddlewareValidationError at startup."""

    def test_sync_function_in_middleware_list_raises_at_startup(self, tmp_path: Path):
        """Sync middleware function raises validation error at startup."""
        # Create _middleware.py with sync function
        mw_content = """
def sync_middleware(request, call_next):
    # This is sync, should be async
    return call_next(request)

middleware = [sync_middleware]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a valid route
        route_dir = tmp_path / "sync-test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        # Should fail validation because middleware is not async
        with pytest.raises(MiddlewareValidationError, match="must be async"):
            create_router_from_path(tmp_path)

    def test_sync_middleware_error_includes_function_name(self, tmp_path: Path):
        """Error message includes the sync function name for debugging."""
        # Create _middleware.py with named sync function
        mw_content = """
def my_logging_middleware(request, call_next):
    return call_next(request)

middleware = [my_logging_middleware]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a route
        route_dir = tmp_path / "logs"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "must be async" in error_message
        assert "my_logging_middleware" in error_message

    def test_mixed_sync_and_async_middleware_raises_at_startup(self, tmp_path: Path):
        """middleware = [async_fn, sync_fn] raises at startup on sync function."""
        # Create _middleware.py with mixed sync and async
        mw_content = """
async def async_middleware(request, call_next):
    return await call_next(request)

def sync_middleware(request, call_next):
    return call_next(request)

middleware = [async_middleware, sync_middleware]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a route
        route_dir = tmp_path / "mixed"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        # Should fail on the sync middleware
        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "must be async" in error_message
        assert "index 1" in error_message

    def test_sync_middleware_validation_uses_iscoroutinefunction(self, tmp_path: Path):
        """Validation checks asyncio.iscoroutinefunction for async detection."""
        # This test documents that we use asyncio.iscoroutinefunction
        # Create regular sync function
        mw_content = """
def not_async(request, call_next):
    pass

middleware = [not_async]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        route_dir = tmp_path / "check"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        # Should catch sync function via asyncio.iscoroutinefunction check
        with pytest.raises(MiddlewareValidationError, match="must be async"):
            create_router_from_path(tmp_path)


class TestRouteHandlerMissingHandler:
    """class handler(route): without handler raises RouteValidationError at import time."""

    def test_route_class_without_handler_raises_at_import(self, tmp_path: Path):
        """class get(route): without handler function raises at module import time."""
        # Create route.py with route class but no handler
        route_content = """
from fastapi_filebased_routing import route

class get(route):
    middleware = []
    # No handler defined!
"""
        route_dir = tmp_path / "broken"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(route_content)

        # This error happens when Python imports the module,
        # which happens during create_router_from_path
        with pytest.raises(RouteValidationError, match="must define.*handler"):
            create_router_from_path(tmp_path)

    def test_missing_handler_error_includes_class_name(self, tmp_path: Path):
        """Error message includes the class name (HTTP method) for debugging."""
        # Create route.py with named class but no handler
        route_content = """
from fastapi_filebased_routing import route

class post(route):
    tags = ["users"]
    # Missing handler!
"""
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(route_content)

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "post" in error_message
        assert "handler" in error_message

    def test_route_class_with_non_callable_handler_raises_at_import(self, tmp_path: Path):
        """class get(route): with handler = "string" raises at module import time."""
        # Create route.py with invalid handler
        route_content = """
from fastapi_filebased_routing import route

class delete(route):
    handler = "not a function"
"""
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(route_content)

        with pytest.raises(RouteValidationError, match="handler must be a callable"):
            create_router_from_path(tmp_path)


class TestMiddlewareHTTPExceptionAtRequestTime:
    """HTTPException in middleware happens at request time, not startup."""

    def test_http_exception_in_middleware_raised_at_request_time(self, tmp_path: Path):
        """Middleware raising HTTPException(403) produces standard error response."""
        # Create _middleware.py that raises HTTPException
        mw_content = """
from fastapi import HTTPException

async def forbidden_middleware(request, call_next):
    raise HTTPException(status_code=403, detail="Access forbidden")

middleware = [forbidden_middleware]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a route that should never execute
        route_dir = tmp_path / "protected"
        route_dir.mkdir()
        route_content = """
async def get():
    return {"should": "never reach here"}
"""
        (route_dir / "route.py").write_text(route_content)

        # Router creation should succeed (no startup error)
        router = create_router_from_path(tmp_path)
        assert router is not None

        # Create test client
        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Request should fail with 403 from middleware
        response = client.get("/protected")
        assert response.status_code == 403
        assert "forbidden" in response.json()["detail"].lower()

    def test_http_exception_prevents_handler_execution(self, tmp_path: Path):
        """HTTPException in middleware short-circuits; handler never executes."""
        # Create _middleware.py that raises HTTPException
        mw_content = """
from fastapi import HTTPException

async def auth_middleware(request, call_next):
    if "Authorization" not in request.headers:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return await call_next(request)

middleware = [auth_middleware]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        # Create a route that would fail if executed
        route_dir = tmp_path / "secure"
        route_dir.mkdir()
        route_content = """
async def get():
    raise RuntimeError("Handler was executed!")
"""
        (route_dir / "route.py").write_text(route_content)

        # Router creation succeeds
        router = create_router_from_path(tmp_path)

        from fastapi import FastAPI

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Request without auth header should fail with 401, not 500 (RuntimeError)
        response = client.get("/secure")
        assert response.status_code == 401
        assert "unauthorized" in response.json()["detail"].lower()


class TestErrorsOccurAtStartup:
    """All middleware errors except HTTPException occur at startup, not request time."""

    def test_non_callable_middleware_fails_before_router_returned(self, tmp_path: Path):
        """Non-callable middleware causes failure DURING create_router_from_path."""
        mw_content = """
middleware = [123]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        router = None
        with pytest.raises(MiddlewareValidationError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created with invalid middleware"

    def test_sync_middleware_fails_before_router_returned(self, tmp_path: Path):
        """Sync middleware causes failure DURING create_router_from_path."""
        mw_content = """
def sync_mw(request, call_next):
    return call_next(request)

middleware = [sync_mw]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        router = None
        with pytest.raises(MiddlewareValidationError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created with sync middleware"

    def test_import_failure_fails_before_router_returned(self, tmp_path: Path):
        """Import failure in _middleware.py causes failure DURING create_router_from_path."""
        mw_content = """
import nonexistent_module
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        router = None
        with pytest.raises(MiddlewareValidationError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created with import failures"

    def test_missing_handler_fails_before_router_returned(self, tmp_path: Path):
        """Missing handler in route class causes failure DURING create_router_from_path."""
        route_content = """
from fastapi_filebased_routing import route

class get(route):
    pass  # No handler!
"""
        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(route_content)

        router = None
        with pytest.raises(RouteValidationError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created with missing handlers"


class TestErrorMessageQuality:
    """Error messages are descriptive and actionable."""

    def test_non_callable_error_message_is_actionable(self, tmp_path: Path):
        """Error for non-callable middleware tells developer what's wrong."""
        mw_content = """
middleware = [42, "string"]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Should say what went wrong
        assert "Non-callable" in message
        # Should include file path
        assert "_middleware.py" in message
        # Should include index
        assert "index" in message

    def test_sync_middleware_error_message_is_actionable(self, tmp_path: Path):
        """Error for sync middleware explains that middleware must be async."""
        mw_content = """
def my_middleware(request, call_next):
    return call_next(request)

middleware = [my_middleware]
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Should say middleware must be async
        assert "must be async" in message
        # Should include function name
        assert "my_middleware" in message
        # Should include file path
        assert "_middleware.py" in message

    def test_import_failure_error_message_includes_details(self, tmp_path: Path):
        """Error for import failure includes file path and original error."""
        mw_content = """
import nonexistent_package_xyz
"""
        (tmp_path / "_middleware.py").write_text(mw_content)

        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text("async def get(): return {}")

        with pytest.raises(MiddlewareValidationError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Should say it failed to import
        assert "Failed to import" in message
        # Should include file path
        assert "_middleware.py" in message

    def test_missing_handler_error_message_is_actionable(self, tmp_path: Path):
        """Error for missing handler tells developer what's needed."""
        route_content = """
from fastapi_filebased_routing import route

class patch(route):
    tags = ["items"]
    # No handler!
"""
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(route_content)

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Should mention the class name
        assert "patch" in message
        # Should explain what's needed
        assert "handler" in message
