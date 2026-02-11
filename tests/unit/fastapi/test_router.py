"""Tests for the FastAPI router adapter module."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    RouteDiscoveryError,
    RouteFilterError,
)
from fastapi_filebased_routing.fastapi.router import (
    DEFAULT_STATUS_CODES,
    create_router_from_path,
)


class TestDefaultStatusCodes:
    """Test the DEFAULT_STATUS_CODES configuration."""

    def test_post_defaults_to_201(self):
        assert DEFAULT_STATUS_CODES["post"] == 201

    def test_delete_defaults_to_204(self):
        assert DEFAULT_STATUS_CODES["delete"] == 204

    def test_other_methods_not_in_dict(self):
        assert "get" not in DEFAULT_STATUS_CODES
        assert "put" not in DEFAULT_STATUS_CODES
        assert "patch" not in DEFAULT_STATUS_CODES


class TestBasicRouteDiscovery:
    """Test basic HTTP route registration."""

    def test_basic_get_handler_discovered_and_registered(self, tmp_path: Path, create_route_file):
        """Basic GET handler is discovered and registered."""
        create_route_file(
            content="""
def get():
    return {"message": "Hello"}
""",
            parent_dir=tmp_path,
            subdir="users",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/users")
        assert response.status_code == 200
        assert response.json() == {"message": "Hello"}

    def test_async_handler_works(self, tmp_path: Path, create_route_file):
        """Async handlers are properly registered."""
        create_route_file(
            content="""
async def get():
    return {"async": True}
""",
            parent_dir=tmp_path,
            subdir="async",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/async")
        assert response.status_code == 200
        assert response.json() == {"async": True}

    def test_multiple_handlers_in_one_file(self, tmp_path: Path, create_route_file):
        """Multiple HTTP methods in one route.py are all registered."""
        create_route_file(
            content="""
def get():
    return {"method": "GET"}

def post():
    return {"method": "POST"}

def delete():
    return None
""",
            parent_dir=tmp_path,
            subdir="items",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        assert client.get("/items").json() == {"method": "GET"}
        assert client.post("/items").json() == {"method": "POST"}
        assert client.delete("/items").status_code == 204


class TestStatusCodes:
    """Test convention-based status code assignment."""

    def test_post_handler_gets_201_status_code(self, tmp_path: Path, create_route_file):
        """POST handler gets 201 Created by default."""
        create_route_file(
            content="""
def post():
    return {"created": True}
""",
            parent_dir=tmp_path,
            subdir="resources",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.post("/resources")
        assert response.status_code == 201

    def test_delete_handler_gets_204_status_code(self, tmp_path: Path, create_route_file):
        """DELETE handler gets 204 No Content by default."""
        create_route_file(
            content="""
def delete():
    return None
""",
            parent_dir=tmp_path,
            subdir="resources",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.delete("/resources")
        assert response.status_code == 204

    def test_get_handler_gets_200_status_code(self, tmp_path: Path, create_route_file):
        """GET handler gets 200 OK (default FastAPI behavior)."""
        create_route_file(
            content="""
def get():
    return {"data": "value"}
""",
            parent_dir=tmp_path,
            subdir="data",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/data")
        assert response.status_code == 200

    def test_put_handler_gets_200_status_code(self, tmp_path: Path, create_route_file):
        """PUT handler gets 200 OK (default FastAPI behavior)."""
        create_route_file(
            content="""
def put():
    return {"updated": True}
""",
            parent_dir=tmp_path,
            subdir="resources",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.put("/resources")
        assert response.status_code == 200

    def test_patch_handler_gets_200_status_code(self, tmp_path: Path, create_route_file):
        """PATCH handler gets 200 OK (default FastAPI behavior)."""
        create_route_file(
            content="""
def patch():
    return {"patched": True}
""",
            parent_dir=tmp_path,
            subdir="resources",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.patch("/resources")
        assert response.status_code == 200


class TestTagDerivation:
    """Test automatic tag derivation from path segments."""

    def test_tags_derived_from_first_path_segment(self, tmp_path: Path, create_route_file):
        """Tags are derived from the first meaningful path segment."""
        create_route_file(
            content="""
def get():
    return {}
""",
            parent_dir=tmp_path,
            subdir="users",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        openapi = app.openapi()
        tags = openapi["paths"]["/users"]["get"]["tags"]
        assert "users" in tags

    def test_tags_skip_dynamic_parameters(self, tmp_path: Path, create_route_file):
        """Tags derived skip dynamic parameters."""
        create_route_file(
            content="""
def get(user_id: str):
    return {"user_id": user_id}
""",
            parent_dir=tmp_path,
            subdir="users/[user_id]",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        openapi = app.openapi()
        tags = openapi["paths"]["/users/{user_id}"]["get"]["tags"]
        assert "users" in tags

    def test_tags_derived_from_nested_static_segment(self, tmp_path: Path, create_route_file):
        """For nested routes, tag is first non-parameter segment."""
        create_route_file(
            content="""
def get(version: str):
    return {}
""",
            parent_dir=tmp_path,
            subdir="api/[version]/users",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        openapi = app.openapi()
        tags = openapi["paths"]["/api/{version}/users"]["get"]["tags"]
        assert "api" in tags

    def test_custom_tags_override_auto_derived(self, tmp_path: Path, create_route_file):
        """Custom TAGS metadata overrides auto-derived tags."""
        create_route_file(
            content="""
TAGS = ["custom-tag", "another-tag"]

def get():
    return {}
""",
            parent_dir=tmp_path,
            subdir="users",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        openapi = app.openapi()
        tags = openapi["paths"]["/users"]["get"]["tags"]
        assert "custom-tag" in tags
        assert "another-tag" in tags
        assert "users" not in tags


class TestMetadataApplication:
    """Test OpenAPI metadata application (SUMMARY, DEPRECATED, docstrings)."""

    def test_summary_applied_from_metadata(self, tmp_path: Path, create_route_file):
        """SUMMARY metadata is applied as route summary."""
        create_route_file(
            content="""
SUMMARY = "Get all users"

def get():
    return []
""",
            parent_dir=tmp_path,
            subdir="users",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        openapi = app.openapi()
        summary = openapi["paths"]["/users"]["get"]["summary"]
        assert summary == "Get all users"

    def test_deprecated_marks_route_as_deprecated(self, tmp_path: Path, create_route_file):
        """DEPRECATED=True marks route as deprecated."""
        create_route_file(
            content="""
DEPRECATED = True

def get():
    return {"old": True}
""",
            parent_dir=tmp_path,
            subdir="old",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        openapi = app.openapi()
        deprecated = openapi["paths"]["/old"]["get"]["deprecated"]
        assert deprecated is True

    def test_handler_docstring_used_as_description(self, tmp_path: Path, create_route_file):
        """Handler docstring is used as OpenAPI description."""
        create_route_file(
            content='''
def get():
    """This is a detailed description of the endpoint."""
    return {}
''',
            parent_dir=tmp_path,
            subdir="docs",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        openapi = app.openapi()
        description = openapi["paths"]["/docs"]["get"]["description"]
        assert "detailed description" in description


class TestPrefixApplication:
    """Test prefix parameter for all routes."""

    def test_prefix_applied_to_all_routes(self, tmp_path: Path, create_route_file):
        """Prefix is applied to all discovered routes."""
        create_route_file(
            content="""
def get():
    return {"status": "ok"}
""",
            parent_dir=tmp_path,
            subdir="health",
        )

        router = create_router_from_path(tmp_path, prefix="/api/v1")

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.status_code == 200


class TestNestedRoutes:
    """Test nested routes with dynamic parameters."""

    def test_nested_routes_with_dynamic_parameters(self, tmp_path: Path, create_route_file):
        """Nested routes with parameters are properly registered."""
        create_route_file(
            content="""
def get(workspace_id: str):
    return {"workspace_id": workspace_id}
""",
            parent_dir=tmp_path,
            subdir="workspaces/[workspace_id]",
        )

        create_route_file(
            content="""
def get(workspace_id: str, project_id: str):
    return {"workspace_id": workspace_id, "project_id": project_id}
""",
            parent_dir=tmp_path,
            subdir="workspaces/[workspace_id]/projects/[project_id]",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/workspaces/ws1")
        assert response.json() == {"workspace_id": "ws1"}

        response = client.get("/workspaces/ws1/projects/proj1")
        assert response.json() == {"workspace_id": "ws1", "project_id": "proj1"}


class TestDuplicateDetection:
    """Test duplicate route detection and error handling."""

    def test_duplicate_route_error_when_same_path_and_method(
        self, tmp_path: Path, create_route_file
    ):
        """DuplicateRouteError raised when same path+method registered twice."""
        # Create two route files with optional params that generate same variant
        create_route_file(
            content="""
def get():
    return {"variant": "1"}
""",
            parent_dir=tmp_path,
            subdir="users",
        )

        # Create a duplicate in a different location
        create_route_file(
            content="""
def get():
    return {"variant": "2"}
""",
            parent_dir=tmp_path,
            subdir="(group)/users",
        )

        with pytest.raises(DuplicateRouteError) as exc_info:
            create_router_from_path(tmp_path)

        error_msg = str(exc_info.value)
        assert "Duplicate route" in error_msg
        assert "GET /users" in error_msg


class TestErrorHandling:
    """Test error handling for invalid inputs."""

    def test_route_discovery_error_for_nonexistent_base_path(self, tmp_path: Path):
        """RouteDiscoveryError raised for non-existent base path."""
        nonexistent = tmp_path / "does-not-exist"

        with pytest.raises(RouteDiscoveryError) as exc_info:
            create_router_from_path(nonexistent)

        assert "does not exist" in str(exc_info.value)

    def test_route_discovery_error_for_file_not_directory(self, tmp_path: Path, create_route_file):
        """RouteDiscoveryError raised when base path is a file."""
        file_path = tmp_path / "file.txt"
        file_path.write_text("not a directory")

        with pytest.raises(RouteDiscoveryError) as exc_info:
            create_router_from_path(file_path)

        assert "not a directory" in str(exc_info.value)

    def test_empty_directory_returns_empty_router(self, tmp_path: Path):
        """Empty directory with no routes returns empty router."""
        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        # Router should have no routes
        assert len(router.routes) == 0

    def test_route_file_with_no_handlers_silently_skipped(self, tmp_path: Path, create_route_file):
        """Route.py with no handlers is silently skipped."""
        create_route_file(
            content="""
# Just a comment, no handlers
TAGS = ["test"]
""",
            parent_dir=tmp_path,
            subdir="empty",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        # No routes should be registered
        assert len(router.routes) == 0


class TestRouterCoexistence:
    """Test that file-based router coexists with manually added routes."""

    def test_router_coexists_with_manual_routes(self, tmp_path: Path, create_route_file):
        """File-based router works alongside manually defined routes."""
        create_route_file(
            content="""
def get():
    return {"auto": True}
""",
            parent_dir=tmp_path,
            subdir="auto",
        )

        router = create_router_from_path(tmp_path)

        # Add manual route to the same router
        @router.get("/manual")
        def manual_route():
            return {"manual": True}

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Both routes should work
        assert client.get("/auto").json() == {"auto": True}
        assert client.get("/manual").json() == {"manual": True}


class TestWebSocketRegistration:
    """Test WebSocket route registration."""

    def test_websocket_handler_registered(self, tmp_path: Path, create_route_file):
        """WebSocket handler is registered via router.websocket()."""
        create_route_file(
            content="""
from fastapi import WebSocket

async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"connected": True})
    await websocket.close()
""",
            parent_dir=tmp_path,
            subdir="ws",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with client.websocket_connect("/ws") as websocket:
            data = websocket.receive_json()
            assert data == {"connected": True}

    def test_websocket_with_http_handlers_in_same_file(self, tmp_path: Path, create_route_file):
        """WebSocket and HTTP handlers can coexist in same route.py."""
        create_route_file(
            content="""
from fastapi import WebSocket

def get():
    return {"type": "http"}

async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_text("ws")
    await websocket.close()
""",
            parent_dir=tmp_path,
            subdir="mixed",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # HTTP endpoint should work
        assert client.get("/mixed").json() == {"type": "http"}

        # WebSocket endpoint should work
        with client.websocket_connect("/mixed") as websocket:
            data = websocket.receive_text()
            assert data == "ws"

    def test_websocket_only_route(self, tmp_path: Path, create_route_file):
        """WebSocket-only route.py works correctly."""
        create_route_file(
            content="""
from fastapi import WebSocket

async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.close()
""",
            parent_dir=tmp_path,
            subdir="wsonly",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with client.websocket_connect("/wsonly"):
            pass  # Connection successful

    def test_websocket_with_dynamic_parameter(self, tmp_path: Path, create_route_file):
        """WebSocket handler with dynamic path parameter."""
        create_route_file(
            content="""
from fastapi import WebSocket

async def websocket(websocket: WebSocket, room_id: str):
    await websocket.accept()
    await websocket.send_text(f"room:{room_id}")
    await websocket.close()
""",
            parent_dir=tmp_path,
            subdir="chat/[room_id]",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        with client.websocket_connect("/chat/lobby") as websocket:
            data = websocket.receive_text()
            assert data == "room:lobby"

    def test_websocket_metadata_not_applied(self, tmp_path: Path, create_route_file):
        """WebSocket routes don't apply HTTP-specific metadata."""
        create_route_file(
            content="""
from fastapi import WebSocket

TAGS = ["websocket-tag"]
SUMMARY = "WebSocket endpoint"
DEPRECATED = True

async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.close()
""",
            parent_dir=tmp_path,
            subdir="wsmeta",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)

        # WebSocket should still work (metadata just ignored)
        client = TestClient(app)
        with client.websocket_connect("/wsmeta"):
            pass  # Connection successful

    def test_websocket_with_middleware_emits_warning(
        self, tmp_path: Path, create_route_file, caplog
    ):
        """WebSocket handler with applicable middleware emits warning."""
        import logging

        # Create directory middleware
        mw_dir = tmp_path / "ws"
        mw_dir.mkdir()
        (mw_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n    return await call_next(request)\n"
        )

        create_route_file(
            content="""
from fastapi import WebSocket

async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.close()
""",
            parent_dir=tmp_path,
            subdir="ws",
        )

        with caplog.at_level(logging.WARNING, logger="fastapi_filebased_routing.fastapi.router"):
            router = create_router_from_path(tmp_path)

        # Warning should be emitted
        assert any(
            "WebSocket" in record.message and "middleware" in record.message.lower()
            for record in caplog.records
        )

        # WebSocket should still work
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)
        with client.websocket_connect("/ws"):
            pass

    def test_websocket_without_middleware_no_warning(
        self, tmp_path: Path, create_route_file, caplog
    ):
        """WebSocket handler without middleware does NOT emit warning."""
        import logging

        create_route_file(
            content="""
from fastapi import WebSocket

async def websocket(websocket: WebSocket):
    await websocket.accept()
    await websocket.close()
""",
            parent_dir=tmp_path,
            subdir="ws_clean",
        )

        with caplog.at_level(logging.WARNING, logger="fastapi_filebased_routing.fastapi.router"):
            create_router_from_path(tmp_path)

        # No warning should be emitted
        assert not any("WebSocket" in record.message for record in caplog.records)


class TestLoadDirectoryMiddleware:
    """Test _load_directory_middleware() helper function."""

    def test_loads_middleware_from_list(self, tmp_path: Path):
        """Loads middleware from _middleware.py with middleware = [fn1, fn2] list."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

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

        middleware_files = [
            MiddlewareFile(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = _load_directory_middleware(middleware_files, tmp_path)

        assert mw_dir in result
        assert len(result[mw_dir]) == 2
        assert callable(result[mw_dir][0])
        assert callable(result[mw_dir][1])

    def test_handles_single_callable(self, tmp_path: Path):
        """Handles middleware = single_fn (single callable)."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

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

        middleware_files = [
            MiddlewareFile(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = _load_directory_middleware(middleware_files, tmp_path)

        assert mw_dir in result
        assert len(result[mw_dir]) == 1
        assert callable(result[mw_dir][0])

    def test_handles_inline_function(self, tmp_path: Path):
        """Handles inline async def middleware(request, call_next) function."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

        # Create _middleware.py with inline function definition
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
async def middleware(request, call_next):
    response = await call_next(request)
    return response
""")

        middleware_files = [
            MiddlewareFile(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = _load_directory_middleware(middleware_files, tmp_path)

        assert mw_dir in result
        assert len(result[mw_dir]) == 1
        assert callable(result[mw_dir][0])

    def test_raises_error_when_import_fails(self, tmp_path: Path):
        """Raises MiddlewareValidationError when _middleware.py fails to import."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.exceptions import MiddlewareValidationError
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

        # Create _middleware.py with syntax error
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
async def middleware(request, call_next):
    # Syntax error
    return await call_next(request
""")

        middleware_files = [
            MiddlewareFile(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        with pytest.raises(MiddlewareValidationError) as exc_info:
            _load_directory_middleware(middleware_files, tmp_path)

        assert "Failed to import" in str(exc_info.value)

    def test_raises_error_for_non_callable_middleware(self, tmp_path: Path):
        """Raises MiddlewareValidationError when middleware contains non-callable."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.exceptions import MiddlewareValidationError
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

        # Create _middleware.py with non-callable in list
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
middleware = ["not_a_function"]
""")

        middleware_files = [
            MiddlewareFile(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        with pytest.raises(MiddlewareValidationError) as exc_info:
            _load_directory_middleware(middleware_files, tmp_path)

        assert "Non-callable middleware" in str(exc_info.value)

    def test_raises_error_for_sync_middleware(self, tmp_path: Path):
        """Raises MiddlewareValidationError for sync middleware."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.exceptions import MiddlewareValidationError
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

        # Create _middleware.py with sync function
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
def sync_middleware(request, call_next):
    return call_next(request)

middleware = sync_middleware
""")

        middleware_files = [
            MiddlewareFile(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        with pytest.raises(MiddlewareValidationError) as exc_info:
            _load_directory_middleware(middleware_files, tmp_path)

        assert "must be async" in str(exc_info.value)

    def test_returns_empty_dict_for_empty_list(self, tmp_path: Path):
        """Returns empty dict for empty list."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

        # Create _middleware.py with empty list
        mw_dir = tmp_path / "api"
        mw_dir.mkdir()
        mw_file = mw_dir / "_middleware.py"
        mw_file.write_text("""
middleware = []
""")

        middleware_files = [
            MiddlewareFile(
                file_path=mw_file,
                directory=mw_dir,
                depth=1,
            )
        ]

        result = _load_directory_middleware(middleware_files, tmp_path)

        # Empty list means no middleware for that directory
        assert mw_dir in result
        assert len(result[mw_dir]) == 0

    def test_handles_multiple_directory_middleware_files(self, tmp_path: Path):
        """Handles multiple directory middleware files."""
        from fastapi_filebased_routing.core.scanner import MiddlewareFile
        from fastapi_filebased_routing.fastapi.router import _load_directory_middleware

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

        middleware_files = [
            MiddlewareFile(file_path=mw_file1, directory=mw_dir1, depth=1),
            MiddlewareFile(file_path=mw_file2, directory=mw_dir2, depth=2),
        ]

        result = _load_directory_middleware(middleware_files, tmp_path)

        assert len(result) == 2
        assert mw_dir1 in result
        assert mw_dir2 in result
        assert len(result[mw_dir1]) == 1
        assert len(result[mw_dir2]) == 1


class TestCollectDirectoryMiddleware:
    """Test _collect_directory_middleware() helper function."""

    def test_collects_from_base_to_route_dir(self, tmp_path: Path):
        """Collects middleware from base to route dir."""
        from fastapi_filebased_routing.fastapi.router import _collect_directory_middleware

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

        result = _collect_directory_middleware(
            route_dir=sub_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        assert len(result) == 2
        assert result[0] == base_mw
        assert result[1] == sub_mw

    def test_sibling_directory_middleware_does_not_apply(self, tmp_path: Path):
        """Sibling directory middleware does NOT apply."""
        from fastapi_filebased_routing.fastapi.router import _collect_directory_middleware

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

        result = _collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        # No middleware should be collected from sibling
        assert len(result) == 0

    def test_route_group_middleware_applies_within_group(self, tmp_path: Path):
        """Route group (name)/ middleware applies within group."""
        from fastapi_filebased_routing.fastapi.router import _collect_directory_middleware

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

        result = _collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        assert len(result) == 1
        assert result[0] == group_mw

    def test_no_directory_middleware_returns_empty_tuple(self, tmp_path: Path):
        """No directory middleware returns empty tuple."""
        from fastapi_filebased_routing.fastapi.router import _collect_directory_middleware

        route_dir = tmp_path / "api" / "users"
        route_dir.mkdir(parents=True)

        result = _collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware={},
        )

        assert result == ()

    def test_multiple_levels_ordered_correctly(self, tmp_path: Path):
        """Multiple levels ordered correctly (parent before child)."""
        from fastapi_filebased_routing.fastapi.router import _collect_directory_middleware

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

        result = _collect_directory_middleware(
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
        from fastapi_filebased_routing.fastapi.router import _collect_directory_middleware

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

        result = _collect_directory_middleware(
            route_dir=route_dir,
            base_path=tmp_path,
            dir_middleware=dir_middleware,
        )

        # Should only have base and users middleware
        assert len(result) == 2
        assert result[0] == base_mw
        assert result[1] == users_mw


class TestMakeMiddlewareRoute:
    """Test _make_middleware_route() helper function."""

    def test_returns_subclass_of_apiroute(self, tmp_path: Path):
        """Returns a subclass of APIRoute."""
        from fastapi.routing import APIRoute

        from fastapi_filebased_routing.fastapi.router import _make_middleware_route

        async def mw(request, call_next):
            return await call_next(request)

        route_class = _make_middleware_route([mw])

        assert issubclass(route_class, APIRoute)
        assert route_class != APIRoute

    def test_middleware_wraps_handlers(self, tmp_path: Path, create_route_file):
        """Middleware wraps handlers (use FastAPI TestClient)."""

        # Create route with middleware
        create_route_file(
            content="""
from fastapi import Request

async def auth_mw(request: Request, call_next):
    request.state.authenticated = True
    response = await call_next(request)
    return response

middleware = [auth_mw]

def get(request: Request):
    return {"authenticated": getattr(request.state, "authenticated", False)}
""",
            parent_dir=tmp_path,
            subdir="protected",
        )

        router = create_router_from_path(tmp_path)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/protected")
        assert response.json() == {"authenticated": True}

    def test_middleware_receives_request_object(self, tmp_path: Path, create_route_file):
        """Middleware receives Request object."""
        # Create route with middleware that checks request
        create_route_file(
            content="""
from fastapi import Request

async def path_mw(request: Request, call_next):
    # Middleware can access request properties
    assert hasattr(request, "url")
    assert hasattr(request, "method")
    response = await call_next(request)
    return response

middleware = [path_mw]

def get():
    return {"ok": True}
""",
            parent_dir=tmp_path,
            subdir="test",
        )

        router = create_router_from_path(tmp_path)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/test")
        assert response.status_code == 200

    def test_context_enrichment_via_request_state(self, tmp_path: Path, create_route_file):
        """Context enrichment (request.state modifications visible)."""
        # Create route with middleware that enriches context
        create_route_file(
            content="""
from fastapi import Request

async def context_mw(request: Request, call_next):
    request.state.user_id = "user123"
    request.state.role = "admin"
    response = await call_next(request)
    return response

middleware = [context_mw]

def get(request: Request):
    return {
        "user_id": request.state.user_id,
        "role": request.state.role,
    }
""",
            parent_dir=tmp_path,
            subdir="context",
        )

        router = create_router_from_path(tmp_path)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/context")
        assert response.json() == {"user_id": "user123", "role": "admin"}

    def test_response_modification(self, tmp_path: Path, create_route_file):
        """Response modification (middleware can alter response)."""
        # Create route with middleware that modifies response
        create_route_file(
            content="""
from fastapi import Request, Response

async def header_mw(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Custom-Header"] = "middleware-value"
    return response

middleware = [header_mw]

def get():
    return {"data": "value"}
""",
            parent_dir=tmp_path,
            subdir="headers",
        )

        router = create_router_from_path(tmp_path)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/headers")
        assert response.headers["X-Custom-Header"] == "middleware-value"
        assert response.json() == {"data": "value"}

    def test_short_circuit_without_call_next(self, tmp_path: Path, create_route_file):
        """Short-circuit (returning without call_next)."""
        # Create route with middleware that short-circuits
        create_route_file(
            content="""
from fastapi import Request
from fastapi.responses import JSONResponse

async def auth_mw(request: Request, call_next):
    # Short-circuit if no auth header
    if "Authorization" not in request.headers:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized"}
        )
    response = await call_next(request)
    return response

middleware = [auth_mw]

def get():
    return {"message": "This should not be reached"}
""",
            parent_dir=tmp_path,
            subdir="auth",
        )

        router = create_router_from_path(tmp_path)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        # Request without authorization header should be short-circuited
        response = client.get("/auth")
        assert response.status_code == 401
        assert response.json() == {"error": "Unauthorized"}

        # Request with authorization header should proceed
        response = client.get("/auth", headers={"Authorization": "Bearer token"})
        assert response.status_code == 200
        assert response.json() == {"message": "This should not be reached"}

    def test_path_params_still_work_with_middleware(self, tmp_path: Path, create_route_file):
        """Path params still work with middleware wrapping."""
        # Create route with path parameters and middleware
        create_route_file(
            content="""
from fastapi import Request

async def log_mw(request: Request, call_next):
    request.state.logged = True
    response = await call_next(request)
    return response

middleware = [log_mw]

def get(user_id: str, request: Request):
    return {
        "user_id": user_id,
        "logged": request.state.logged,
    }
""",
            parent_dir=tmp_path,
            subdir="users/[user_id]",
        )

        router = create_router_from_path(tmp_path)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/users/123")
        assert response.json() == {"user_id": "123", "logged": True}

    def test_multiple_middleware_execute_in_correct_order(self, tmp_path: Path, create_route_file):
        """Multiple middleware execute in correct order."""
        # Create route with multiple middleware
        create_route_file(
            content="""
from fastapi import Request

async def mw1(request: Request, call_next):
    request.state.order = ["mw1_before"]
    response = await call_next(request)
    return response

async def mw2(request: Request, call_next):
    request.state.order.append("mw2_before")
    response = await call_next(request)
    return response

async def mw3(request: Request, call_next):
    request.state.order.append("mw3_before")
    response = await call_next(request)
    return response

middleware = [mw1, mw2, mw3]

def get(request: Request):
    request.state.order.append("handler")
    return {"order": request.state.order}
""",
            parent_dir=tmp_path,
            subdir="order",
        )

        router = create_router_from_path(tmp_path)
        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/order")
        # Middleware should execute in order: mw1 -> mw2 -> mw3 -> handler
        assert response.json() == {"order": ["mw1_before", "mw2_before", "mw3_before", "handler"]}


class TestRouteFiltering:
    """Test include/exclude route filtering in create_router_from_path."""

    def test_include_filters_routes(self, tmp_path: Path, create_route_file):
        """Only included routes get registered."""
        create_route_file(
            content='def get():\n    return {"route": "users"}\n',
            parent_dir=tmp_path,
            subdir="users",
        )
        create_route_file(
            content='def get():\n    return {"route": "admin"}\n',
            parent_dir=tmp_path,
            subdir="admin",
        )

        router = create_router_from_path(tmp_path, include=["users"])

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        assert client.get("/users").status_code == 200
        assert client.get("/users").json() == {"route": "users"}
        assert client.get("/admin").status_code == 404

    def test_exclude_filters_routes(self, tmp_path: Path, create_route_file):
        """Excluded routes return 404."""
        create_route_file(
            content='def get():\n    return {"route": "users"}\n',
            parent_dir=tmp_path,
            subdir="users",
        )
        create_route_file(
            content='def get():\n    return {"route": "admin"}\n',
            parent_dir=tmp_path,
            subdir="admin",
        )

        router = create_router_from_path(tmp_path, exclude=["admin"])

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        assert client.get("/users").status_code == 200
        assert client.get("/admin").status_code == 404

    def test_both_raises_error(self, tmp_path: Path, create_route_file):
        """Providing both include and exclude raises RouteFilterError."""
        create_route_file(
            content="def get():\n    return {}\n",
            parent_dir=tmp_path,
            subdir="users",
        )

        with pytest.raises(RouteFilterError, match="Cannot specify both"):
            create_router_from_path(tmp_path, include=["users"], exclude=["admin"])

    def test_none_means_no_filter(self, tmp_path: Path, create_route_file):
        """Default None params mean no filtering (backward compatible)."""
        create_route_file(
            content='def get():\n    return {"route": "users"}\n',
            parent_dir=tmp_path,
            subdir="users",
        )
        create_route_file(
            content='def get():\n    return {"route": "admin"}\n',
            parent_dir=tmp_path,
            subdir="admin",
        )

        router = create_router_from_path(tmp_path)

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        assert client.get("/users").status_code == 200
        assert client.get("/admin").status_code == 200

    def test_middleware_not_imported_for_excluded_dirs(self, tmp_path: Path, create_route_file):
        """Middleware in excluded directories is not loaded."""
        # Create admin dir with middleware that would fail if imported
        admin_dir = tmp_path / "admin"
        admin_dir.mkdir()
        (admin_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Admin"] = "true"\n'
            "    return response\n"
        )
        create_route_file(
            content='def get():\n    return {"route": "admin"}\n',
            parent_dir=tmp_path,
            subdir="admin",
        )
        create_route_file(
            content='def get():\n    return {"route": "users"}\n',
            parent_dir=tmp_path,
            subdir="users",
        )

        router = create_router_from_path(tmp_path, exclude=["admin"])

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/users")
        assert response.status_code == 200
        # Admin middleware should NOT have run
        assert "X-Admin" not in response.headers

    def test_ancestor_middleware_applies_to_included_routes(
        self, tmp_path: Path, create_route_file
    ):
        """Root/parent middleware still applies to included child routes."""
        # Root middleware
        (tmp_path / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Root"] = "true"\n'
            "    return response\n"
        )
        create_route_file(
            content='def get():\n    return {"route": "users"}\n',
            parent_dir=tmp_path,
            subdir="users",
        )
        create_route_file(
            content='def get():\n    return {"route": "admin"}\n',
            parent_dir=tmp_path,
            subdir="admin",
        )

        router = create_router_from_path(tmp_path, include=["users"])

        app = FastAPI()
        app.include_router(router)
        client = TestClient(app)

        response = client.get("/users")
        assert response.status_code == 200
        assert response.headers["X-Root"] == "true"
