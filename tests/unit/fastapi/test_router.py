"""Tests for the FastAPI router adapter module."""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    RouteDiscoveryError,
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

    def test_basic_get_handler_discovered_and_registered(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_delete_handler_gets_204_status_code(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_patch_handler_gets_200_status_code(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_tags_derived_from_first_path_segment(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_tags_derived_from_nested_static_segment(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_deprecated_marks_route_as_deprecated(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_handler_docstring_used_as_description(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_nested_routes_with_dynamic_parameters(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_route_discovery_error_for_file_not_directory(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_route_file_with_no_handlers_silently_skipped(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_router_coexists_with_manual_routes(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_websocket_with_http_handlers_in_same_file(
        self, tmp_path: Path, create_route_file
    ):
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

    def test_websocket_with_dynamic_parameter(
        self, tmp_path: Path, create_route_file
    ):
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
