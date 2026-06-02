"""Tests for the adapter registration module (FastAPI-specific registration).

Covers DEFAULT_STATUS_CODES, derive_tags, resolve_handler -> ResolvedHandler
(including the None-vs-explicit status_code distinction), and the
make_middleware_route APIRoute factory.
"""

from typing import Any

from fastapi.routing import APIRoute

from fastapi_filebased_routing.adapter.registration import (
    DEFAULT_STATUS_CODES,
    ResolvedHandler,
    derive_tags,
    make_middleware_route,
    resolve_handler,
)
from fastapi_filebased_routing.core.routes import RouteConfig


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


class TestDeriveTags:
    """Test pure tag derivation from a URL path."""

    def test_first_static_segment(self):
        assert derive_tags("/users/{id}") == ["users"]

    def test_first_non_parameter_segment(self):
        assert derive_tags("/api/{version}/users") == ["api"]

    def test_only_parameter_returns_root(self):
        assert derive_tags("/{id}") == ["root"]

    def test_root_path_returns_root(self):
        assert derive_tags("/") == ["root"]


class TestResolveHandler:
    """Test resolve_handler() and the ResolvedHandler result."""

    def test_plain_handler_get_has_no_default_status(self):
        """A plain GET handler resolves with status_code None (FastAPI default)."""

        async def handler() -> dict:
            return {}

        resolved = resolve_handler(handler, "get", ["tag"], "summary", False)

        assert isinstance(resolved, ResolvedHandler)
        assert resolved.handler is handler
        assert resolved.middleware == ()
        assert resolved.tags == ["tag"]
        assert resolved.summary == "summary"
        assert resolved.deprecated is False
        # GET has no convention default -> stays None so it never reaches add_api_route
        assert resolved.status_code is None

    def test_post_handler_gets_201_default(self):
        """A plain POST handler resolves with the 201 convention default."""

        async def handler() -> dict:
            return {}

        resolved = resolve_handler(handler, "post", [], None, False)
        assert resolved.status_code == 201

    def test_delete_handler_gets_204_default(self):
        """A plain DELETE handler resolves with the 204 convention default."""

        async def handler() -> dict:
            return {}

        resolved = resolve_handler(handler, "delete", [], None, False)
        assert resolved.status_code == 204

    def test_route_config_unwrapped(self):
        """A RouteConfig is unwrapped into handler + middleware + metadata."""

        async def inner() -> dict:
            return {}

        async def mw(request: Any, call_next: Any) -> Any:
            return await call_next(request)

        config = RouteConfig(
            handler=inner,
            middleware=(mw,),
            tags=("cfg-tag",),
            summary="cfg-summary",
            deprecated=True,
            status_code=418,
        )

        resolved = resolve_handler(config, "get", ["default"], "default-summary", False)

        assert resolved.handler is inner
        assert resolved.middleware == (mw,)
        assert resolved.tags == ["cfg-tag"]
        assert resolved.summary == "cfg-summary"
        assert resolved.deprecated is True
        assert resolved.status_code == 418

    def test_route_config_explicit_status_overrides_convention(self):
        """An explicit RouteConfig.status_code overrides the POST convention."""

        async def inner() -> dict:
            return {}

        config = RouteConfig(handler=inner, status_code=202)
        resolved = resolve_handler(config, "post", [], None, False)
        assert resolved.status_code == 202

    def test_route_config_none_status_keeps_convention(self):
        """A RouteConfig with status_code None keeps the convention default."""

        async def inner() -> dict:
            return {}

        config = RouteConfig(handler=inner, status_code=None)
        resolved = resolve_handler(config, "post", [], None, False)
        # None status_code in config -> falls back to POST convention (201)
        assert resolved.status_code == 201

    def test_route_config_none_metadata_keeps_defaults(self):
        """RouteConfig None tags/summary fall back to the supplied defaults."""

        async def inner() -> dict:
            return {}

        config = RouteConfig(handler=inner, tags=None, summary=None)
        resolved = resolve_handler(config, "get", ["default"], "default-summary", False)
        assert resolved.tags == ["default"]
        assert resolved.summary == "default-summary"


class TestMakeMiddlewareRoute:
    """Test make_middleware_route() factory."""

    def test_returns_subclass_of_apiroute(self):
        """Returns a subclass of APIRoute."""

        async def mw(request: Any, call_next: Any) -> Any:
            return await call_next(request)

        route_class = make_middleware_route([mw])

        assert issubclass(route_class, APIRoute)
        assert route_class is not APIRoute
