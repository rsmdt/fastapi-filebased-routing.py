"""Integration tests for dispatch() in the middleware pipeline.

Verifies that dispatch() adapts class-based middleware for use in
_middleware.py files, tested end-to-end via create_router_from_path
and FastAPI TestClient.
"""

from pathlib import Path
from textwrap import dedent

from fastapi import FastAPI
from fastapi.testclient import TestClient

from fastapi_filebased_routing import create_router_from_path


class TestDispatchInMiddlewareFile:
    """End-to-end test: dispatch() used inside a real _middleware.py."""

    def test_dispatch_in_middleware_file(self, tmp_path: Path) -> None:
        """Class-based middleware via dispatch() should modify responses."""
        api_dir = tmp_path / "api"
        api_dir.mkdir()

        # _middleware.py that uses dispatch() with a class-based middleware
        (api_dir / "_middleware.py").write_text(
            dedent("""\
            from fastapi_filebased_routing import dispatch

            class HeaderMiddleware:
                def __init__(self, app, header_name="X-Custom", header_value="hello"):
                    self.app = app
                    self.header_name = header_name
                    self.header_value = header_value

                async def dispatch(self, request, call_next):
                    response = await call_next(request)
                    response.headers[self.header_name] = self.header_value
                    return response

            middleware = [
                dispatch(HeaderMiddleware, header_name="X-Dispatch", header_value="works"),
            ]
        """)
        )

        # A route under api/
        items_dir = api_dir / "items"
        items_dir.mkdir()
        (items_dir / "route.py").write_text('async def get():\n    return {"items": []}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/items")

        assert response.status_code == 200
        assert response.json() == {"items": []}
        assert response.headers["X-Dispatch"] == "works"

    def test_dispatch_mixed_with_function_middleware(self, tmp_path: Path) -> None:
        """dispatch() should work alongside plain function middleware."""
        api_dir = tmp_path / "api"
        api_dir.mkdir()

        (api_dir / "_middleware.py").write_text(
            dedent("""\
            from fastapi_filebased_routing import dispatch

            async def add_source_header(request, call_next):
                response = await call_next(request)
                response.headers["X-Source"] = "function"
                return response

            class TagMiddleware:
                def __init__(self, app, tag="default"):
                    self.app = app
                    self.tag = tag

                async def dispatch(self, request, call_next):
                    response = await call_next(request)
                    response.headers["X-Tag"] = self.tag
                    return response

            middleware = [
                add_source_header,
                dispatch(TagMiddleware, tag="class-based"),
            ]
        """)
        )

        items_dir = api_dir / "items"
        items_dir.mkdir()
        (items_dir / "route.py").write_text('async def get():\n    return {"ok": True}\n')

        app = FastAPI()
        router = create_router_from_path(tmp_path)
        app.include_router(router)

        client = TestClient(app)
        response = client.get("/api/items")

        assert response.status_code == 200
        assert response.headers["X-Source"] == "function"
        assert response.headers["X-Tag"] == "class-based"
