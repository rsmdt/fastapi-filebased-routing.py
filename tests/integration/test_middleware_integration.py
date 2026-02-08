"""Integration tests for the middleware system.

Tests the full middleware pipeline: directory, file, and handler-level middleware
using FastAPI TestClient with real temporary directory structures.

Each test creates a temporary directory structure with route.py and/or _middleware.py
files, calls create_router_from_path to build the router, mounts it on a FastAPI app,
and uses TestClient to make requests and verify behavior.
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_filebased_routing import create_router_from_path

# ---------------------------------------------------------------------------
# 1. Directory Middleware Tests
# ---------------------------------------------------------------------------


class TestDirectoryMiddleware:
    """Verify directory-level middleware via _middleware.py files."""

    def test_directory_middleware_applies_to_all_routes_in_subtree(self, tmp_path: Path) -> None:
        # Create _middleware.py at api/ level
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-API-Middleware"] = "applied"\n'
            "    return response\n"
        )

        # Create routes under api/
        users_dir = api_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text('async def get():\n    return {"resource": "users"}\n')

        posts_dir = api_dir / "posts"
        posts_dir.mkdir()
        (posts_dir / "route.py").write_text('async def get():\n    return {"resource": "posts"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Both routes should have the directory middleware header
        users_response = client.get("/api/users")
        assert users_response.status_code == 200
        assert users_response.headers["X-API-Middleware"] == "applied"

        posts_response = client.get("/api/posts")
        assert posts_response.status_code == 200
        assert posts_response.headers["X-API-Middleware"] == "applied"

    def test_parent_directory_middleware_executes_before_child(self, tmp_path: Path) -> None:
        # Root middleware
        (tmp_path / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}root,"\n'
            "    return response\n"
        )

        # api/ middleware
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}api,"\n'
            "    return response\n"
        )

        # api/v1/ middleware
        v1_dir = api_dir / "v1"
        v1_dir.mkdir()
        (v1_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}v1,"\n'
            "    return response\n"
        )

        # Route at api/v1/health
        health_dir = v1_dir / "health"
        health_dir.mkdir()
        (health_dir / "route.py").write_text('async def get():\n    return {"status": "ok"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/v1/health")

        assert response.status_code == 200
        # Response flows back: v1 → api → root
        # So headers are appended in reverse order
        assert response.headers["X-Order"] == "v1,api,root,"

    def test_sibling_directories_do_not_share_middleware(self, tmp_path: Path) -> None:
        # api/ middleware
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-API-Middleware"] = "applied"\n'
            "    return response\n"
        )
        users_dir = api_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text('async def get():\n    return {"resource": "users"}\n')

        # public/ (sibling to api/) has no middleware
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        health_dir = public_dir / "health"
        health_dir.mkdir()
        (health_dir / "route.py").write_text('async def get():\n    return {"status": "ok"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # /api/users has the middleware
        api_response = client.get("/api/users")
        assert api_response.status_code == 200
        assert api_response.headers.get("X-API-Middleware") == "applied"

        # /public/health does NOT have the middleware
        public_response = client.get("/public/health")
        assert public_response.status_code == 200
        assert "X-API-Middleware" not in public_response.headers


# ---------------------------------------------------------------------------
# 2. File-Level Middleware Tests
# ---------------------------------------------------------------------------


class TestFileLevelMiddleware:
    """Verify file-level middleware via module-level `middleware = [...]`."""

    def test_file_middleware_applies_to_all_handlers_in_file(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "async def file_middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-File-Middleware"] = "applied"\n'
            "    return response\n"
            "\n"
            "middleware = [file_middleware]\n"
            "\n"
            "async def get():\n"
            '    return {"items": []}\n'
            "\n"
            "async def post():\n"
            '    return {"id": 1}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Both handlers share the file-level middleware
        get_response = client.get("/items")
        assert get_response.status_code == 200
        assert get_response.headers["X-File-Middleware"] == "applied"

        post_response = client.post("/items")
        assert post_response.status_code == 201
        assert post_response.headers["X-File-Middleware"] == "applied"

    def test_file_middleware_stacks_after_directory_middleware(self, tmp_path: Path) -> None:
        # Directory middleware
        (tmp_path / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}dir,"\n'
            "    return response\n"
        )

        # File middleware
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "async def file_mw(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}file,"\n'
            "    return response\n"
            "\n"
            "middleware = [file_mw]\n"
            "\n"
            "async def get():\n"
            '    return {"users": []}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/users")

        assert response.status_code == 200
        # Response flows back: file → dir
        assert response.headers["X-Order"] == "file,dir,"


# ---------------------------------------------------------------------------
# 3. Handler-Level Middleware Tests
# ---------------------------------------------------------------------------


class TestHandlerLevelMiddleware:
    """Verify handler-level middleware via `class handler(route):` blocks."""

    def test_handler_middleware_applies_to_single_handler(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "resources"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "from fastapi_filebased_routing.core.middleware import route\n"
            "\n"
            "async def _handler_mw(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Handler-Middleware"] = "applied"\n'
            "    return response\n"
            "\n"
            "class post(route):\n"
            "    middleware = [_handler_mw]\n"
            "\n"
            "    async def handler():\n"
            '        return {"created": True}\n'
            "\n"
            "async def get():\n"
            '    return {"items": []}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # POST has handler middleware
        post_response = client.post("/resources")
        assert post_response.status_code == 201
        assert post_response.headers["X-Handler-Middleware"] == "applied"

        # GET does not have handler middleware
        get_response = client.get("/resources")
        assert get_response.status_code == 200
        assert "X-Handler-Middleware" not in get_response.headers

    def test_handler_middleware_stacks_after_file_middleware(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "from fastapi_filebased_routing.core.middleware import route\n"
            "\n"
            "async def _file_mw(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}file,"\n'
            "    return response\n"
            "\n"
            "async def _handler_mw(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}handler,"\n'
            "    return response\n"
            "\n"
            "middleware = [_file_mw]\n"
            "\n"
            "class post(route):\n"
            "    middleware = [_handler_mw]\n"
            "\n"
            "    async def handler():\n"
            '        return {"created": True}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.post("/items")

        assert response.status_code == 201
        # Response flows back: handler → file
        assert response.headers["X-Order"] == "handler,file,"


# ---------------------------------------------------------------------------
# 4. Full Execution Order Tests
# ---------------------------------------------------------------------------


class TestFullExecutionOrder:
    """Verify complete middleware execution order across all layers."""

    def test_full_middleware_stack_execution_order(self, tmp_path: Path) -> None:
        # Root directory middleware
        (tmp_path / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}dir-root,"\n'
            "    return response\n"
        )

        # api/ directory middleware
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}dir-api,"\n'
            "    return response\n"
        )

        # File with file-level and handler-level middleware
        users_dir = api_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text(
            "from fastapi_filebased_routing.core.middleware import route\n"
            "\n"
            "async def _file_mw(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}file,"\n'
            "    return response\n"
            "\n"
            "async def _handler_mw(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}handler,"\n'
            "    return response\n"
            "\n"
            "middleware = [_file_mw]\n"
            "\n"
            "class post(route):\n"
            "    middleware = [_handler_mw]\n"
            "\n"
            "    async def handler():\n"
            '        return {"created": True}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.post("/api/users")

        assert response.status_code == 201
        # Response flows back through middleware in reverse order:
        # handler → file → dir-api → dir-root
        assert response.headers["X-Order"] == "handler,file,dir-api,dir-root,"


# ---------------------------------------------------------------------------
# 5. Context Enrichment Tests
# ---------------------------------------------------------------------------


class TestContextEnrichment:
    """Verify middleware can enrich request context for downstream handlers."""

    def test_middleware_sets_request_state_for_handler(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "protected"
        route_dir.mkdir()
        (route_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    # Simulate authentication\n"
            '    request.state.user = {"id": "user123", "role": "admin"}\n'
            "    response = await call_next(request)\n"
            "    return response\n"
        )

        (route_dir / "route.py").write_text(
            "from fastapi import Request\n"
            "\n"
            "async def get(request: Request):\n"
            "    user = request.state.user\n"
            '    return {"user_id": user["id"], "role": user["role"]}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/protected")

        assert response.status_code == 200
        assert response.json() == {"user_id": "user123", "role": "admin"}

    def test_chained_middleware_context_enrichment(self, tmp_path: Path) -> None:
        # First middleware sets user
        (tmp_path / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            '    request.state.user_id = "user456"\n'
            "    response = await call_next(request)\n"
            "    return response\n"
        )

        # Second middleware uses user_id to set permissions
        route_dir = tmp_path / "data"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "from fastapi import Request\n"
            "\n"
            "async def permissions_mw(request, call_next):\n"
            "    user_id = request.state.user_id\n"
            '    request.state.permissions = ["read", "write"] if user_id == "user456" else ["read"]\n'
            "    response = await call_next(request)\n"
            "    return response\n"
            "\n"
            "middleware = [permissions_mw]\n"
            "\n"
            "async def get(request: Request):\n"
            "    return {\n"
            '        "user_id": request.state.user_id,\n'
            '        "permissions": request.state.permissions\n'
            "    }\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/data")

        assert response.status_code == 200
        assert response.json() == {"user_id": "user456", "permissions": ["read", "write"]}


# ---------------------------------------------------------------------------
# 6. Mixed Handler Types Tests
# ---------------------------------------------------------------------------


class TestMixedHandlerTypes:
    """Verify plain functions and RouteConfig handlers coexist in same file."""

    def test_plain_function_and_route_class_in_same_file(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "mixed"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "from fastapi_filebased_routing.core.middleware import route\n"
            "\n"
            "async def _handler_mw(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Handler-Middleware"] = "applied"\n'
            "    return response\n"
            "\n"
            "async def get():\n"
            '    return {"handler": "plain-get"}\n'
            "\n"
            "class post(route):\n"
            "    middleware = [_handler_mw]\n"
            "\n"
            "    async def handler():\n"
            '        return {"handler": "route-post"}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Plain GET has no middleware
        get_response = client.get("/mixed")
        assert get_response.status_code == 200
        assert get_response.json() == {"handler": "plain-get"}
        assert "X-Handler-Middleware" not in get_response.headers

        # RouteConfig POST has middleware
        post_response = client.post("/mixed")
        assert post_response.status_code == 201
        assert post_response.json() == {"handler": "route-post"}
        assert post_response.headers["X-Handler-Middleware"] == "applied"


# ---------------------------------------------------------------------------
# 7. Inline Middleware Tests
# ---------------------------------------------------------------------------


class TestInlineMiddleware:
    """Verify inline middleware definition in _middleware.py."""

    def test_inline_middleware_function_in_middleware_file(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "api"
        route_dir.mkdir()
        (route_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Inline-Middleware"] = "applied"\n'
            "    return response\n"
        )

        users_dir = route_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text('async def get():\n    return {"users": []}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/users")

        assert response.status_code == 200
        assert response.headers["X-Inline-Middleware"] == "applied"


# ---------------------------------------------------------------------------
# 8. Empty Middleware Tests
# ---------------------------------------------------------------------------


class TestEmptyMiddleware:
    """Verify empty middleware lists are no-ops."""

    def test_empty_middleware_list_is_noop(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            'middleware = []\n\nasync def get():\n    return {"items": []}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/items")

        assert response.status_code == 200
        assert response.json() == {"items": []}


# ---------------------------------------------------------------------------
# 9. No Middleware Tests (Backward Compatibility)
# ---------------------------------------------------------------------------


class TestNoMiddleware:
    """Verify routes without middleware work exactly as v0.1.0."""

    def test_route_without_middleware_works_as_v0_1_0(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "users"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "async def get():\n"
            '    return {"users": ["alice", "bob"]}\n'
            "\n"
            "async def post():\n"
            '    return {"id": 1, "name": "charlie"}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        get_response = client.get("/users")
        assert get_response.status_code == 200
        assert get_response.json() == {"users": ["alice", "bob"]}

        post_response = client.post("/users")
        assert post_response.status_code == 201
        assert post_response.json() == {"id": 1, "name": "charlie"}

    def test_multiple_routes_without_middleware(self, tmp_path: Path) -> None:
        # Multiple resource directories, none with middleware
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
            response = client.get(f"/{resource}")
            assert response.status_code == 200
            assert response.json() == {resource: []}


# ---------------------------------------------------------------------------
# 10. Middleware with Path Parameters
# ---------------------------------------------------------------------------


class TestMiddlewareWithPathParameters:
    """Verify middleware works correctly with dynamic path parameters."""

    def test_middleware_with_dynamic_path_parameter(self, tmp_path: Path) -> None:
        users_dir = tmp_path / "users" / "[user_id]"
        users_dir.mkdir(parents=True)

        # Middleware at the [user_id] level
        (users_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-User-Middleware"] = "applied"\n'
            "    return response\n"
        )

        (users_dir / "route.py").write_text(
            'async def get(user_id: str):\n    return {"user_id": user_id}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/users/alice123")

        assert response.status_code == 200
        assert response.json() == {"user_id": "alice123"}
        assert response.headers["X-User-Middleware"] == "applied"


# ---------------------------------------------------------------------------
# 11. Middleware Response Modification Tests
# ---------------------------------------------------------------------------


class TestMiddlewareResponseModification:
    """Verify middleware can modify responses before returning them."""

    def test_middleware_modifies_response_headers(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "api"
        route_dir.mkdir()
        (route_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Custom-Header"] = "custom-value"\n'
            '    response.headers["X-Powered-By"] = "fastapi-filebased-routing"\n'
            "    return response\n"
        )

        (route_dir / "route.py").write_text('async def get():\n    return {"data": "test"}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api")

        assert response.status_code == 200
        assert response.headers["X-Custom-Header"] == "custom-value"
        assert response.headers["X-Powered-By"] == "fastapi-filebased-routing"


# ---------------------------------------------------------------------------
# 12. Multiple Middleware in Same Level
# ---------------------------------------------------------------------------


class TestMultipleMiddlewareInSameLevel:
    """Verify multiple middleware at the same level execute in list order."""

    def test_multiple_file_middleware_execute_in_order(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "items"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "async def mw1(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}mw1,"\n'
            "    return response\n"
            "\n"
            "async def mw2(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}mw2,"\n'
            "    return response\n"
            "\n"
            "async def mw3(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}mw3,"\n'
            "    return response\n"
            "\n"
            "middleware = [mw1, mw2, mw3]\n"
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
        # Response flows back through middleware: mw3 → mw2 → mw1
        assert response.headers["X-Order"] == "mw3,mw2,mw1,"

    def test_multiple_handler_middleware_execute_in_order(self, tmp_path: Path) -> None:
        route_dir = tmp_path / "resources"
        route_dir.mkdir()
        (route_dir / "route.py").write_text(
            "from fastapi_filebased_routing.core.middleware import route\n"
            "\n"
            "async def _mw1(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}mw1,"\n'
            "    return response\n"
            "\n"
            "async def _mw2(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    order = response.headers.get("X-Order", "")\n'
            '    response.headers["X-Order"] = f"{order}mw2,"\n'
            "    return response\n"
            "\n"
            "class post(route):\n"
            "    middleware = [_mw1, _mw2]\n"
            "\n"
            "    async def handler():\n"
            '        return {"created": True}\n'
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.post("/resources")

        assert response.status_code == 201
        # Response flows back: mw2 → mw1
        assert response.headers["X-Order"] == "mw2,mw1,"


# ---------------------------------------------------------------------------
# 13. Middleware with Route Groups
# ---------------------------------------------------------------------------


class TestMiddlewareWithRouteGroups:
    """Verify middleware works correctly with route groups (parentheses)."""

    def test_middleware_in_route_group_applies_to_group_routes(self, tmp_path: Path) -> None:
        admin_dir = tmp_path / "(admin)"
        admin_dir.mkdir()
        (admin_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Admin-Middleware"] = "applied"\n'
            "    return response\n"
        )

        settings_dir = admin_dir / "settings"
        settings_dir.mkdir()
        (settings_dir / "route.py").write_text('async def get():\n    return {"settings": {}}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        # Route group is excluded from URL path
        response = client.get("/settings")

        assert response.status_code == 200
        assert response.headers["X-Admin-Middleware"] == "applied"


# ---------------------------------------------------------------------------
# 14. Comprehensive Integration Test
# ---------------------------------------------------------------------------


class TestComprehensiveIntegration:
    """Full integration test covering all middleware features together."""

    def test_realistic_api_with_all_middleware_features(self, tmp_path: Path) -> None:
        # Root middleware for all routes
        (tmp_path / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Root"] = "true"\n'
            "    return response\n"
        )

        # Public routes (no auth)
        public_dir = tmp_path / "public"
        public_dir.mkdir()
        health_dir = public_dir / "health"
        health_dir.mkdir()
        (health_dir / "route.py").write_text('async def get():\n    return {"status": "ok"}\n')

        # API routes with authentication
        api_dir = tmp_path / "api"
        api_dir.mkdir()
        (api_dir / "_middleware.py").write_text(
            "async def middleware(request, call_next):\n"
            "    # Simulate authentication\n"
            "    request.state.authenticated = True\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Authenticated"] = "true"\n'
            "    return response\n"
        )

        # Users resource with file-level rate limiting
        users_dir = api_dir / "users"
        users_dir.mkdir()
        (users_dir / "route.py").write_text(
            "from fastapi import Request\n"
            "from fastapi_filebased_routing.core.middleware import route\n"
            "\n"
            "async def rate_limit(request, call_next):\n"
            "    response = await call_next(request)\n"
            '    response.headers["X-Rate-Limited"] = "true"\n'
            "    return response\n"
            "\n"
            "middleware = [rate_limit]\n"
            "\n"
            "async def get(request: Request):\n"
            '    return {"users": [], "authenticated": request.state.authenticated}\n'
            "\n"
            "class post(route):\n"
            "    # Handler-specific middleware for admin check\n"
            "    async def admin_check(request, call_next):\n"
            "        request.state.is_admin = True\n"
            "        response = await call_next(request)\n"
            '        response.headers["X-Admin-Checked"] = "true"\n'
            "        return response\n"
            "\n"
            "    middleware = [admin_check]\n"
            "\n"
            "    async def handler(request: Request):\n"
            "        return {\n"
            '            "created": True,\n'
            '            "authenticated": request.state.authenticated,\n'
            '            "is_admin": request.state.is_admin\n'
            "        }\n"
        )

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)

        # Public health check - only root middleware
        health_response = client.get("/public/health")
        assert health_response.status_code == 200
        assert health_response.headers["X-Root"] == "true"
        assert "X-Authenticated" not in health_response.headers
        assert "X-Rate-Limited" not in health_response.headers

        # API users GET - root + api + file middleware
        users_get = client.get("/api/users")
        assert users_get.status_code == 200
        assert users_get.headers["X-Root"] == "true"
        assert users_get.headers["X-Authenticated"] == "true"
        assert users_get.headers["X-Rate-Limited"] == "true"
        assert "X-Admin-Checked" not in users_get.headers
        assert users_get.json()["authenticated"] is True

        # API users POST - root + api + file + handler middleware
        users_post = client.post("/api/users")
        assert users_post.status_code == 201
        assert users_post.headers["X-Root"] == "true"
        assert users_post.headers["X-Authenticated"] == "true"
        assert users_post.headers["X-Rate-Limited"] == "true"
        assert users_post.headers["X-Admin-Checked"] == "true"
        assert users_post.json()["authenticated"] is True
        assert users_post.json()["is_admin"] is True
