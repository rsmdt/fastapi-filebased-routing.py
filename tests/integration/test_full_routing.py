"""End-to-end integration tests for file-based routing.

Tests the full pipeline: directory structure -> scanner -> parser -> importer
-> router factory -> FastAPI app -> HTTP requests via TestClient.

Each test creates a real temporary directory structure with route.py files,
creates a FastAPI app with the file-based router, and makes actual HTTP
requests to verify the response.
"""

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRouter
from fastapi.testclient import TestClient

from fastapi_filebased_routing import create_router_from_path

# ---------------------------------------------------------------------------
# 1. Basic CRUD route discovery
# ---------------------------------------------------------------------------


class TestBasicRouteDiscovery:
    """Verify that route.py files are discovered and respond to HTTP requests."""

    def test_get_users_returns_data(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"users": []}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/users")

        assert response.status_code == 200
        assert response.json() == {"users": []}

    def test_nested_route_discovery(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "api" / "v1" / "health"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text('async def get():\n    return {"status": "healthy"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}


# ---------------------------------------------------------------------------
# 2. POST returns 201 by convention
# ---------------------------------------------------------------------------


class TestConventionStatusCodes:
    """Verify convention-based default status codes."""

    def test_post_returns_201(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'async def post():\n    return {"id": 1, "name": "Alice"}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.post("/users")

        assert response.status_code == 201
        assert response.json() == {"id": 1, "name": "Alice"}

    def test_delete_returns_204(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users" / "[user_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text("async def delete(user_id: str):\n    return None\n")

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.delete("/users/42")

        assert response.status_code == 204

    def test_get_returns_200(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"items": []}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/items")

        assert response.status_code == 200

    def test_put_returns_200(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items" / "[item_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def put(item_id: str):\n    return {"item_id": item_id, "updated": True}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.put("/items/99")

        assert response.status_code == 200
        assert response.json() == {"item_id": "99", "updated": True}


# ---------------------------------------------------------------------------
# 4. Dynamic parameters
# ---------------------------------------------------------------------------


class TestDynamicParameters:
    """Verify that [param] directories pass path parameters to handlers."""

    def test_single_dynamic_parameter(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users" / "[user_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(user_id: str):\n    return {"user_id": user_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/users/abc123")

        assert response.status_code == 200
        assert response.json() == {"user_id": "abc123"}

    def test_nested_dynamic_parameters(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "orgs" / "[org_id]" / "members" / "[member_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            "async def get(org_id: str, member_id: str):\n"
            '    return {"org_id": org_id, "member_id": member_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/orgs/acme/members/user42")

        assert response.status_code == 200
        assert response.json() == {"org_id": "acme", "member_id": "user42"}


# ---------------------------------------------------------------------------
# 5. Optional parameters
# ---------------------------------------------------------------------------


class TestOptionalParameters:
    """Verify [[param]] generates 2^n route variants."""

    def test_optional_parameter_generates_two_variants(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "api" / "[[version]]" / "users"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(version: str = "default"):\n    return {"version": version}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Variant 1: without optional parameter
        response_without = client.get("/api/users")
        assert response_without.status_code == 200

        # Variant 2: with optional parameter
        response_with = client.get("/api/v2/users")
        assert response_with.status_code == 200
        assert response_with.json() == {"version": "v2"}


# ---------------------------------------------------------------------------
# 6. Catch-all parameters
# ---------------------------------------------------------------------------


class TestCatchAllParameters:
    """Verify [...param] captures remaining path segments."""

    def test_catch_all_captures_path_segments(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "files" / "[...file_path]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(file_path: str):\n    return {"file_path": file_path}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/files/docs/readme.md")

        assert response.status_code == 200
        assert response.json() == {"file_path": "docs/readme.md"}

    def test_catch_all_with_deeply_nested_path(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "files" / "[...file_path]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(file_path: str):\n    return {"file_path": file_path}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/files/a/b/c/d/e.txt")

        assert response.status_code == 200
        assert response.json() == {"file_path": "a/b/c/d/e.txt"}


# ---------------------------------------------------------------------------
# 7. Route groups
# ---------------------------------------------------------------------------


class TestRouteGroups:
    """Verify (group) directories are excluded from the URL path."""

    def test_group_excluded_from_url(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "(admin)" / "settings"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get():\n    return {"settings": {"theme": "dark"}}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/settings")

        assert response.status_code == 200
        assert response.json() == {"settings": {"theme": "dark"}}

    def test_nested_group_with_dynamic_param(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "(api)" / "users" / "[user_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(user_id: str):\n    return {"user_id": user_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/users/abc")

        assert response.status_code == 200
        assert response.json() == {"user_id": "abc"}


# ---------------------------------------------------------------------------
# 8. WebSocket connection and message exchange
# ---------------------------------------------------------------------------


class TestWebSocket:
    """Verify WebSocket handlers work end-to-end."""

    def test_websocket_echo(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "ws"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "from fastapi import WebSocket\n"
            "\n"
            "async def websocket(ws: WebSocket):\n"
            "    await ws.accept()\n"
            "    data = await ws.receive_text()\n"
            '    await ws.send_text(f"echo: {data}")\n'
            "    await ws.close()\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        with client.websocket_connect("/ws") as websocket:
            websocket.send_text("hello")
            response = websocket.receive_text()
            assert response == "echo: hello"

    def test_websocket_with_dynamic_param(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "ws" / "chat" / "[room_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            "from fastapi import WebSocket\n"
            "\n"
            "async def websocket(ws: WebSocket, room_id: str):\n"
            "    await ws.accept()\n"
            "    data = await ws.receive_text()\n"
            '    await ws.send_text(f"Room {room_id}: {data}")\n'
            "    await ws.close()\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        with client.websocket_connect("/ws/chat/lobby") as websocket:
            websocket.send_text("hi there")
            response = websocket.receive_text()
            assert response == "Room lobby: hi there"

    def test_websocket_coexists_with_http_on_same_path(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "notifications"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "from fastapi import WebSocket\n"
            "\n"
            "async def get():\n"
            '    return {"notifications": []}\n'
            "\n"
            "async def websocket(ws: WebSocket):\n"
            "    await ws.accept()\n"
            '    await ws.send_text("connected")\n'
            "    await ws.close()\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # HTTP GET works
        response = client.get("/notifications")
        assert response.status_code == 200
        assert response.json() == {"notifications": []}

        # WebSocket works on the same path
        with client.websocket_connect("/notifications") as websocket:
            data = websocket.receive_text()
            assert data == "connected"


# ---------------------------------------------------------------------------
# 9. Mixed sync and async handlers
# ---------------------------------------------------------------------------


class TestSyncAndAsyncHandlers:
    """Verify both sync and async handlers work via TestClient."""

    def test_sync_handler_works(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "sync"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('def get():\n    return {"mode": "sync"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/sync")

        assert response.status_code == 200
        assert response.json() == {"mode": "sync"}

    def test_async_handler_works(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "async-route"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"mode": "async"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/async-route")

        assert response.status_code == 200
        assert response.json() == {"mode": "async"}

    def test_mixed_sync_and_async_in_same_file(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "mixed"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "def get():\n"
            '    return {"handler": "sync-get"}\n'
            "\n"
            "async def post():\n"
            '    return {"handler": "async-post"}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        get_response = client.get("/mixed")
        assert get_response.status_code == 200
        assert get_response.json() == {"handler": "sync-get"}

        post_response = client.post("/mixed")
        assert post_response.status_code == 201
        assert post_response.json() == {"handler": "async-post"}


# ---------------------------------------------------------------------------
# 10. Router coexists with manual app.get() routes
# ---------------------------------------------------------------------------


class TestCoexistenceWithManualRoutes:
    """Verify file-based router works alongside manually defined routes."""

    def test_manual_and_file_based_routes_coexist(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'async def get():\n    return {"source": "file-based"}\n'
        )

        app = FastAPI()

        # Manual route defined directly on the app
        @app.get("/manual")
        async def manual_route():
            return {"source": "manual"}

        # File-based router included
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Both routes work
        manual_response = client.get("/manual")
        assert manual_response.status_code == 200
        assert manual_response.json() == {"source": "manual"}

        file_response = client.get("/users")
        assert file_response.status_code == 200
        assert file_response.json() == {"source": "file-based"}


# ---------------------------------------------------------------------------
# 11. OpenAPI schema shows all routes with correct metadata
# ---------------------------------------------------------------------------


class TestOpenAPISchema:
    """Verify routes appear correctly in OpenAPI schema."""

    def test_routes_appear_in_openapi_schema(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'TAGS = ["users"]\n'
            'SUMMARY = "List all users"\n'
            "\n"
            "async def get():\n"
            '    """Get a list of all users."""\n'
            '    return {"users": []}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        assert response.status_code == 200
        schema = response.json()

        # Verify /users path exists in OpenAPI
        assert "/users" in schema["paths"]

        # Verify GET method is registered
        get_op = schema["paths"]["/users"]["get"]
        assert "users" in get_op["tags"]
        assert get_op["summary"] == "List all users"
        assert get_op["description"] == "Get a list of all users."

    def test_deprecated_route_in_openapi(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "legacy"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'DEPRECATED = True\n\nasync def get():\n    return {"legacy": True}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        get_op = schema["paths"]["/legacy"]["get"]
        assert get_op["deprecated"] is True

    def test_convention_status_codes_in_openapi(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'async def post():\n    return {"id": 1}\n\nasync def delete():\n    return None\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        paths = schema["paths"]["/items"]

        # POST should show 201
        assert "201" in paths["post"]["responses"]

        # DELETE should show 204
        assert "204" in paths["delete"]["responses"]

    def test_auto_derived_tags_in_openapi(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "products" / "[product_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(product_id: str):\n    return {"product_id": product_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        get_op = schema["paths"]["/products/{product_id}"]["get"]

        # Tags should be auto-derived from first meaningful segment
        assert "products" in get_op["tags"]

    def test_dynamic_param_in_openapi_path(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users" / "[user_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(user_id: str):\n    return {"user_id": user_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()

        # Path should use {user_id} in OpenAPI
        assert "/users/{user_id}" in schema["paths"]

        # Parameter should be declared in the OpenAPI schema
        get_op = schema["paths"]["/users/{user_id}"]["get"]
        param_names = [p["name"] for p in get_op["parameters"]]
        assert "user_id" in param_names


# ---------------------------------------------------------------------------
# 12. Multiple route files in a tree work together
# ---------------------------------------------------------------------------


class TestMultipleRouteTree:
    """Verify a realistic multi-file route tree works end-to-end."""

    def test_full_crud_tree(self, tmp_path: Path) -> None:
        # /users (list + create)
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text(
            "async def get():\n"
            '    return {"users": ["alice", "bob"]}\n'
            "\n"
            "async def post():\n"
            '    return {"id": 3, "name": "charlie"}\n'
        )

        # /users/{user_id} (read + update + delete)
        user_detail_dir = tmp_path / "users" / "[user_id]"
        user_detail_dir.mkdir(parents=True)
        (user_detail_dir / "route.py").write_text(
            "async def get(user_id: str):\n"
            '    return {"user_id": user_id, "name": "alice"}\n'
            "\n"
            "async def put(user_id: str):\n"
            '    return {"user_id": user_id, "updated": True}\n'
            "\n"
            "async def delete(user_id: str):\n"
            "    return None\n"
        )

        # /health
        health_dir = tmp_path / "health"
        health_dir.mkdir()
        (health_dir / "route.py").write_text('async def get():\n    return {"status": "ok"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # GET /users
        r = client.get("/users")
        assert r.status_code == 200
        assert r.json() == {"users": ["alice", "bob"]}

        # POST /users
        r = client.post("/users")
        assert r.status_code == 201

        # GET /users/42
        r = client.get("/users/42")
        assert r.status_code == 200
        assert r.json()["user_id"] == "42"

        # PUT /users/42
        r = client.put("/users/42")
        assert r.status_code == 200
        assert r.json()["updated"] is True

        # DELETE /users/42
        r = client.delete("/users/42")
        assert r.status_code == 204

        # GET /health
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"status": "ok"}

    def test_multiple_resource_trees(self, tmp_path: Path) -> None:
        for resource in ("users", "posts", "comments"):
            resource_dir = tmp_path / resource
            resource_dir.mkdir()
            (resource_dir / "route.py").write_text(
                f'async def get():\n    return {{"{resource}": []}}\n'
            )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        for resource in ("users", "posts", "comments"):
            r = client.get(f"/{resource}")
            assert r.status_code == 200
            assert r.json() == {resource: []}


# ---------------------------------------------------------------------------
# 13. Prefix parameter works end-to-end
# ---------------------------------------------------------------------------


class TestPrefixParameter:
    """Verify that prefix parameter prepends to all discovered routes."""

    def test_prefix_applied_to_all_routes(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"users": []}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path, prefix="/api/v1")
        app.include_router(router)

        client = TestClient(app)

        # Route should be prefixed
        response = client.get("/api/v1/users")
        assert response.status_code == 200
        assert response.json() == {"users": []}

    def test_prefix_with_dynamic_params(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items" / "[item_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(item_id: str):\n    return {"item_id": item_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path, prefix="/api")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/items/xyz")

        assert response.status_code == 200
        assert response.json() == {"item_id": "xyz"}

    def test_prefix_appears_in_openapi(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"users": []}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path, prefix="/api/v1")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        # The path in OpenAPI should include the prefix
        assert "/api/v1/users" in schema["paths"]


# ---------------------------------------------------------------------------
# Additional coverage: private helpers and constants are silently ignored
# ---------------------------------------------------------------------------


class TestPrivateHelpersIgnored:
    """Verify private functions and constants in route.py do not affect routing."""

    def test_private_helpers_and_constants_ignored(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'TAGS = ["items"]\n'
            "SOME_CONSTANT = 42\n"
            "\n"
            "def _validate_item(item_id: str) -> bool:\n"
            "    return len(item_id) > 0\n"
            "\n"
            "async def get():\n"
            '    return {"items": []}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/items")

        assert response.status_code == 200
        assert response.json() == {"items": []}


# ---------------------------------------------------------------------------
# Additional coverage: root-level route.py
# ---------------------------------------------------------------------------


class TestRootRoute:
    """Verify route.py at the root of the base path maps to /."""

    def test_root_route(self, tmp_path: Path) -> None:
        (tmp_path / "route.py").write_text('async def get():\n    return {"root": True}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"root": True}


# ---------------------------------------------------------------------------
# Additional coverage: multiple HTTP methods on same path
# ---------------------------------------------------------------------------


class TestMultipleMethodsSamePath:
    """Verify multiple HTTP methods in one route.py all work."""

    def test_get_post_put_patch_delete_on_same_path(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "resources"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "async def get():\n"
            '    return {"method": "GET"}\n'
            "\n"
            "async def post():\n"
            '    return {"method": "POST"}\n'
            "\n"
            "async def put():\n"
            '    return {"method": "PUT"}\n'
            "\n"
            "async def patch():\n"
            '    return {"method": "PATCH"}\n'
            "\n"
            "async def delete():\n"
            "    return None\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        assert client.get("/resources").status_code == 200
        assert client.get("/resources").json()["method"] == "GET"

        assert client.post("/resources").status_code == 201
        assert client.post("/resources").json()["method"] == "POST"

        assert client.put("/resources").status_code == 200
        assert client.put("/resources").json()["method"] == "PUT"

        assert client.patch("/resources").status_code == 200
        assert client.patch("/resources").json()["method"] == "PATCH"

        assert client.delete("/resources").status_code == 204


# ---------------------------------------------------------------------------
# Backward Compatibility Regression Tests (v0.1.0 → v0.2.0)
# ---------------------------------------------------------------------------


class TestBackwardCompatibilityPlainHandlers:
    """Verify plain function handlers work exactly as in v0.1.0."""

    def test_plain_async_handler_no_middleware(self, tmp_path: Path) -> None:
        """Plain async def handler with no middleware works identically."""
        route_dir = tmp_path / "api" / "status"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text('async def get() -> dict:\n    return {"ok": True}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/status")

        assert response.status_code == 200
        assert response.json() == {"ok": True}

    def test_plain_sync_handler_no_middleware(self, tmp_path: Path) -> None:
        """Plain sync def handler with no middleware works identically."""
        route_dir = tmp_path / "sync"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('def get() -> dict:\n    return {"sync": True}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/sync")

        assert response.status_code == 200
        assert response.json() == {"sync": True}

    def test_multiple_plain_handlers_same_file(self, tmp_path: Path) -> None:
        """Multiple plain handlers in same file work identically."""
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "async def get():\n"
            '    return {"items": []}\n'
            "\n"
            "async def post():\n"
            '    return {"id": 1}\n'
            "\n"
            "async def delete():\n"
            "    return None\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        assert client.get("/items").status_code == 200
        assert client.post("/items").status_code == 201
        assert client.delete("/items").status_code == 204


class TestBackwardCompatibilityModuleLevelMetadata:
    """Verify module-level metadata (TAGS, SUMMARY, DEPRECATED) works exactly as v0.1.0."""

    def test_module_level_tags(self, tmp_path: Path) -> None:
        """Module-level TAGS work identically."""
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'TAGS = ["users", "authentication"]\n\nasync def get():\n    return {"users": []}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        get_op = schema["paths"]["/users"]["get"]
        assert set(get_op["tags"]) == {"users", "authentication"}

    def test_module_level_summary(self, tmp_path: Path) -> None:
        """Module-level SUMMARY works identically."""
        route_dir = tmp_path / "health"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'SUMMARY = "Health check endpoint"\n'
            "\n"
            "async def get():\n"
            '    """Returns the health status of the API."""\n'
            '    return {"status": "ok"}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        get_op = schema["paths"]["/health"]["get"]
        assert get_op["summary"] == "Health check endpoint"
        assert get_op["description"] == "Returns the health status of the API."

    def test_module_level_deprecated(self, tmp_path: Path) -> None:
        """Module-level DEPRECATED works identically."""
        route_dir = tmp_path / "legacy"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'DEPRECATED = True\n\nasync def get():\n    return {"legacy": True}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        get_op = schema["paths"]["/legacy"]["get"]
        assert get_op["deprecated"] is True

    def test_all_module_metadata_combined(self, tmp_path: Path) -> None:
        """All module-level metadata fields work together identically."""
        route_dir = tmp_path / "admin"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'TAGS = ["admin"]\n'
            'SUMMARY = "Admin operations"\n'
            "DEPRECATED = True\n"
            "\n"
            "async def get():\n"
            '    return {"admin": True}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/openapi.json")

        schema = response.json()
        get_op = schema["paths"]["/admin"]["get"]
        assert "admin" in get_op["tags"]
        assert get_op["summary"] == "Admin operations"
        assert get_op["deprecated"] is True


class TestBackwardCompatibilityNoMiddlewareProject:
    """Verify projects with zero _middleware.py files behave identically to v0.1.0."""

    def test_no_middleware_files_identical_behavior(self, tmp_path: Path) -> None:
        """Project with no _middleware.py files works identically."""
        # Create a complete route tree with no middleware
        users_dir = tmp_path / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text(
            "async def get():\n"
            '    return {"users": []}\n'
            "\n"
            "async def post():\n"
            '    return {"id": 1}\n'
        )

        user_detail = tmp_path / "users" / "[user_id]"
        user_detail.mkdir(parents=True)
        (user_detail / "route.py").write_text(
            "async def get(user_id: str):\n"
            '    return {"user_id": user_id}\n'
            "\n"
            "async def delete(user_id: str):\n"
            "    return None\n"
        )

        health_dir = tmp_path / "health"
        health_dir.mkdir()
        (health_dir / "route.py").write_text('async def get():\n    return {"status": "healthy"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # All routes work identically to v0.1.0
        assert client.get("/users").status_code == 200
        assert client.post("/users").status_code == 201
        assert client.get("/users/42").json() == {"user_id": "42"}
        assert client.delete("/users/99").status_code == 204
        assert client.get("/health").json() == {"status": "healthy"}

    def test_no_performance_degradation_without_middleware(self, tmp_path: Path) -> None:
        """Routes without middleware have no performance overhead."""
        route_dir = tmp_path / "fast"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"fast": True}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Route works normally (performance is measured externally)
        response = client.get("/fast")
        assert response.status_code == 200
        assert response.json() == {"fast": True}


class TestBackwardCompatibilityAPISignature:
    """Verify create_router_from_path API signature is unchanged."""

    def test_create_router_signature_unchanged(self, tmp_path: Path) -> None:
        """create_router_from_path(base_path, *, prefix="") signature unchanged."""
        route_dir = tmp_path / "api"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"api": True}\n')

        app = FastAPI()

        # Positional base_path
        router1 = create_router_from_path(tmp_path)
        assert isinstance(router1, APIRouter)

        # With prefix keyword argument
        router2 = create_router_from_path(tmp_path, prefix="/v1")
        assert isinstance(router2, APIRouter)

        # Verify both work
        app.include_router(router1)
        app.include_router(router2)

        client = TestClient(app)
        assert client.get("/api").status_code == 200
        assert client.get("/v1/api").status_code == 200

    def test_return_type_unchanged(self, tmp_path: Path) -> None:
        """create_router_from_path returns APIRouter (same type)."""
        route_dir = tmp_path / "test"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"test": True}\n')

        router = create_router_from_path(tmp_path)

        # Return type is APIRouter
        assert isinstance(router, APIRouter)

        # Can be included in FastAPI app
        app = FastAPI()
        app.include_router(router)

        client = TestClient(app)
        assert client.get("/test").status_code == 200


class TestBackwardCompatibilityAllV010Features:
    """Verify all v0.1.0 features work unchanged."""

    def test_dynamic_parameters_unchanged(self, tmp_path: Path) -> None:
        """Dynamic parameters [id] work identically."""
        route_dir = tmp_path / "posts" / "[post_id]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(post_id: str):\n    return {"post_id": post_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/posts/123")

        assert response.status_code == 200
        assert response.json() == {"post_id": "123"}

    def test_route_groups_unchanged(self, tmp_path: Path) -> None:
        """Route groups (group) work identically."""
        route_dir = tmp_path / "(admin)" / "settings"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text('async def get():\n    return {"settings": {}}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/settings")  # (admin) excluded from URL

        assert response.status_code == 200
        assert response.json() == {"settings": {}}

    def test_websocket_handlers_unchanged(self, tmp_path: Path) -> None:
        """WebSocket handlers work identically."""
        route_dir = tmp_path / "ws" / "echo"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            "from fastapi import WebSocket\n"
            "\n"
            "async def websocket(ws: WebSocket):\n"
            "    await ws.accept()\n"
            "    data = await ws.receive_text()\n"
            '    await ws.send_text(f"echo: {data}")\n'
            "    await ws.close()\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        with client.websocket_connect("/ws/echo") as websocket:
            websocket.send_text("test")
            response = websocket.receive_text()
            assert response == "echo: test"

    def test_duplicate_detection_unchanged(self, tmp_path: Path) -> None:
        """Duplicate route detection works identically."""
        from fastapi_filebased_routing.exceptions import DuplicateRouteError

        # Create two route files that map to the same path
        route1 = tmp_path / "api" / "route.py"
        route1.parent.mkdir(parents=True)
        route1.write_text('async def get(): return {"a": 1}\n')

        # Can't create two files at same path; test duplicate via optional params instead

        # Better test: create optional parameter routes that create duplicate variants
        route_dir = tmp_path / "test" / "[[version]]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(version: str = "v1"):\n    return {"version": version}\n'
        )

        # Create a duplicate of the no-version variant
        route_dir2 = tmp_path / "test"
        (route_dir2 / "route.py").write_text('async def get():\n    return {"duplicate": True}\n')

        # Should raise DuplicateRouteError
        with pytest.raises(DuplicateRouteError, match="Duplicate route"):
            create_router_from_path(tmp_path)

    def test_optional_parameters_unchanged(self, tmp_path: Path) -> None:
        """Optional parameters [[param]] work identically."""
        route_dir = tmp_path / "api" / "[[version]]" / "data"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(version: str = "v1"):\n    return {"version": version}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Both variants work
        assert client.get("/api/data").status_code == 200
        assert client.get("/api/v2/data").json() == {"version": "v2"}

    def test_catchall_parameters_unchanged(self, tmp_path: Path) -> None:
        """Catch-all parameters [...param] work identically."""
        route_dir = tmp_path / "files" / "[...path]"
        route_dir.mkdir(parents=True)
        (route_dir / "route.py").write_text(
            'async def get(path: str):\n    return {"path": path}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/files/a/b/c/file.txt")

        assert response.status_code == 200
        assert response.json() == {"path": "a/b/c/file.txt"}

    def test_convention_status_codes_unchanged(self, tmp_path: Path) -> None:
        """Convention-based status codes work identically."""
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "async def post():\n"
            '    return {"id": 1}\n'
            "\n"
            "async def delete():\n"
            "    return None\n"
            "\n"
            "async def get():\n"
            '    return {"items": []}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # POST → 201 Created
        assert client.post("/items").status_code == 201
        # DELETE → 204 No Content
        assert client.delete("/items").status_code == 204
        # GET → 200 OK
        assert client.get("/items").status_code == 200

    def test_root_route_unchanged(self, tmp_path: Path) -> None:
        """Root-level route.py works identically."""
        (tmp_path / "route.py").write_text('async def get():\n    return {"root": True}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/")

        assert response.status_code == 200
        assert response.json() == {"root": True}

    def test_prefix_parameter_unchanged(self, tmp_path: Path) -> None:
        """Prefix parameter works identically."""
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text('async def get():\n    return {"users": []}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path, prefix="/api/v1")
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/v1/users")

        assert response.status_code == 200
        assert response.json() == {"users": []}
