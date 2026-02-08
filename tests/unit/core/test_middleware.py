"""Tests for middleware primitives."""

import asyncio
from typing import Any

import pytest

from fastapi_filebased_routing.core.middleware import RouteConfig


def test_route_config_is_frozen() -> None:
    """RouteConfig should be a frozen dataclass."""

    def handler() -> str:
        return "ok"

    config = RouteConfig(handler=handler)

    with pytest.raises(Exception):  # noqa: B017 - FrozenInstanceError or AttributeError
        config.handler = lambda: "modified"  # type: ignore[misc]


def test_route_config_has_expected_fields() -> None:
    """RouteConfig should have all required fields."""

    def handler() -> str:
        return "ok"

    config = RouteConfig(
        handler=handler,
        middleware=[],
        tags=("api", "v1"),
        summary="Test endpoint",
        deprecated=True,
        status_code=201,
    )

    assert config.handler is handler
    assert config.middleware == []
    assert config.tags == ("api", "v1")
    assert config.summary == "Test endpoint"
    assert config.deprecated is True
    assert config.status_code == 201


def test_route_config_default_values() -> None:
    """RouteConfig should have sensible defaults."""

    def handler() -> str:
        return "ok"

    config = RouteConfig(handler=handler)

    assert config.handler is handler
    assert config.middleware == ()
    assert config.tags is None
    assert config.summary is None
    assert config.deprecated is False
    assert config.status_code is None


def test_route_config_is_callable_sync() -> None:
    """RouteConfig should delegate __call__ to handler (sync)."""

    def handler(x: int, y: int) -> int:
        return x + y

    config = RouteConfig(handler=handler)

    result = config(2, 3)
    assert result == 5


def test_route_config_is_callable_async() -> None:
    """RouteConfig should delegate __call__ to handler (async)."""

    async def handler(x: int, y: int) -> int:  # noqa: N805
        await asyncio.sleep(0)
        return x * y

    config = RouteConfig(handler=handler)

    result = asyncio.run(config(4, 5))
    assert result == 20


def test_route_config_preserves_handler_name() -> None:
    """RouteConfig should preserve handler __name__ in __post_init__."""

    def my_handler() -> str:
        return "ok"

    config = RouteConfig(handler=my_handler)

    assert config.__name__ == "my_handler"


def test_route_config_preserves_handler_doc() -> None:
    """RouteConfig should preserve handler __doc__ in __post_init__."""

    def my_handler() -> str:
        """Docstring for my handler."""
        return "ok"

    config = RouteConfig(handler=my_handler)

    assert config.__doc__ == "Docstring for my handler."


def test_route_config_preserves_handler_annotations() -> None:
    """RouteConfig should preserve handler __annotations__ in __post_init__."""

    def my_handler(x: int, y: str) -> bool:
        return len(y) == x

    config = RouteConfig(handler=my_handler)

    assert config.__annotations__ == {"x": int, "y": str, "return": bool}


def test_route_config_preserves_handler_module() -> None:
    """RouteConfig should preserve handler __module__ in __post_init__."""

    def my_handler() -> str:
        return "ok"

    config = RouteConfig(handler=my_handler)

    assert config.__module__ == my_handler.__module__


def test_route_config_sets_wrapped_for_introspection() -> None:
    """RouteConfig should set __wrapped__ for introspection tools."""

    def my_handler() -> str:
        return "ok"

    config = RouteConfig(handler=my_handler)

    assert config.__wrapped__ is my_handler


def test_route_config_with_lambda_handler() -> None:
    """RouteConfig should handle lambda functions gracefully."""
    handler = lambda x: x * 2  # noqa: E731

    config = RouteConfig(handler=handler)

    assert config(5) == 10
    assert config.__name__ == "<lambda>"
    assert config.__wrapped__ is handler


def test_route_config_with_handler_missing_metadata() -> None:
    """RouteConfig should handle handlers missing __doc__ or __annotations__."""

    class CallableClass:
        def __call__(self) -> str:
            return "callable"

    handler = CallableClass()
    config = RouteConfig(handler=handler)

    # Should not raise, should use defaults
    assert hasattr(config, "__name__")
    assert hasattr(config, "__doc__")
    assert hasattr(config, "__annotations__")
    assert config.__wrapped__ is handler


def test_route_config_with_middleware_tuple() -> None:
    """RouteConfig should accept middleware as a tuple."""

    def handler() -> str:
        return "ok"

    def mw1(call_next: Any) -> Any:
        return call_next

    def mw2(call_next: Any) -> Any:
        return call_next

    config = RouteConfig(handler=handler, middleware=(mw1, mw2))

    assert config.middleware == (mw1, mw2)


# === _RouteMeta metaclass and route base class tests ===


def test_route_base_class_creation() -> None:
    """The route base class itself is created normally (no metaclass interception)."""
    from fastapi_filebased_routing.core.middleware import route

    # route class should exist as a normal class
    assert isinstance(route, type)
    assert route.__name__ == "route"


def test_simple_handler_returns_route_config() -> None:
    """class get(route): with handler returns RouteConfig instance."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        async def handler(user_id: str) -> dict:  # noqa: N805
            return {"user_id": user_id}

    # get should be a RouteConfig, not a class
    assert isinstance(get, RouteConfig)
    assert not isinstance(get, type)


def test_route_config_is_callable_via_metaclass() -> None:
    """RouteConfig created via metaclass delegates calls to the wrapped handler."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        async def handler(user_id: str) -> dict:  # noqa: N805
            return {"user_id": user_id}

    # Calling get(...) should delegate to handler
    result = asyncio.run(get(user_id="123"))
    assert result == {"user_id": "123"}


def test_middleware_list_normalized_to_tuple() -> None:
    """Middleware list is normalized to tuple."""
    from fastapi_filebased_routing.core.middleware import route

    async def auth(request: Any) -> None:
        pass

    async def rate_limit(request: Any) -> None:
        pass

    class get(route):  # noqa: N801
        middleware = [auth, rate_limit]

        async def handler() -> dict:
            return {}

    assert get.middleware == (auth, rate_limit)
    assert isinstance(get.middleware, tuple)


def test_single_callable_middleware_normalized_to_tuple() -> None:
    """Single callable middleware is normalized to tuple of one."""
    from fastapi_filebased_routing.core.middleware import route

    async def auth(request: Any) -> None:
        pass

    class get(route):  # noqa: N801
        middleware = auth

        async def handler() -> dict:
            return {}

    assert get.middleware == (auth,)
    assert isinstance(get.middleware, tuple)


def test_none_middleware_normalized_to_empty_tuple() -> None:
    """None middleware is normalized to empty tuple."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        middleware = None

        async def handler() -> dict:
            return {}

    assert get.middleware == ()
    assert isinstance(get.middleware, tuple)


def test_no_middleware_defaults_to_empty_tuple() -> None:
    """Missing middleware defaults to empty tuple."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        async def handler() -> dict:
            return {}

    assert get.middleware == ()
    assert isinstance(get.middleware, tuple)


def test_missing_handler_raises_validation_error() -> None:
    """class get(route): without handler raises RouteValidationError."""
    from fastapi_filebased_routing.core.middleware import route
    from fastapi_filebased_routing.exceptions import RouteValidationError

    with pytest.raises(
        RouteValidationError,
        match=r"class get\(route\) must define an async def handler\(\.\.\.\) function",
    ):

        class get(route):  # noqa: N801
            middleware = []


def test_non_callable_handler_raises_validation_error() -> None:
    """class get(route): with non-callable handler raises RouteValidationError."""
    from fastapi_filebased_routing.core.middleware import route
    from fastapi_filebased_routing.exceptions import RouteValidationError

    with pytest.raises(
        RouteValidationError,
        match=r"class get\(route\): handler must be a callable, got str",
    ):

        class get(route):  # noqa: N801
            handler = "not a function"


def test_invalid_middleware_type_raises_validation_error() -> None:
    """class get(route): with invalid middleware type raises RouteValidationError."""
    from fastapi_filebased_routing.core.middleware import route
    from fastapi_filebased_routing.exceptions import RouteValidationError

    with pytest.raises(
        RouteValidationError,
        match=r"class get\(route\): middleware must be a list or callable, got str",
    ):

        class get(route):  # noqa: N801
            middleware = "invalid"

            async def handler() -> dict:
                return {}


def test_metadata_extraction_tags() -> None:
    """Metadata is extracted: tags."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        tags = ["users", "admin"]

        async def handler() -> dict:
            return {}

    assert get.tags == ("users", "admin")


def test_metadata_extraction_summary() -> None:
    """Metadata is extracted: summary."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        summary = "Get user details"

        async def handler() -> dict:
            return {}

    assert get.summary == "Get user details"


def test_metadata_extraction_deprecated() -> None:
    """Metadata is extracted: deprecated."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        deprecated = True

        async def handler() -> dict:
            return {}

    assert get.deprecated is True


def test_metadata_extraction_status_code() -> None:
    """Metadata is extracted: status_code."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        status_code = 201

        async def handler() -> dict:
            return {}

    assert get.status_code == 201


def test_full_example_with_all_features() -> None:
    """Full example: handler + middleware + metadata."""
    from fastapi_filebased_routing.core.middleware import route

    async def auth(request: Any) -> None:
        pass

    async def rate_limit(request: Any) -> None:
        pass

    class get(route):  # noqa: N801
        middleware = [auth, rate_limit]
        tags = ["users"]
        summary = "Get user"
        deprecated = False
        status_code = 200

        async def handler(user_id: str) -> dict:  # noqa: N805
            return {"user_id": user_id}

    assert isinstance(get, RouteConfig)
    assert get.middleware == (auth, rate_limit)
    assert get.tags == ("users",)
    assert get.summary == "Get user"
    assert get.deprecated is False
    assert get.status_code == 200


def test_tuple_middleware_preserved() -> None:
    """Middleware as tuple is preserved."""
    from fastapi_filebased_routing.core.middleware import route

    async def auth(request: Any) -> None:
        pass

    class get(route):  # noqa: N801
        middleware = (auth,)

        async def handler() -> dict:
            return {}

    assert get.middleware == (auth,)
    assert isinstance(get.middleware, tuple)


def test_deprecated_defaults_to_false() -> None:
    """deprecated defaults to False if not specified."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        async def handler() -> dict:
            return {}

    assert get.deprecated is False


def test_handler_metadata_preserved() -> None:
    """Handler metadata is preserved on RouteConfig."""
    from fastapi_filebased_routing.core.middleware import route

    class get(route):  # noqa: N801
        async def handler(user_id: str) -> dict:  # noqa: N805
            """Retrieve user details."""
            return {"user_id": user_id}

    assert get.__name__ == "handler"
    assert get.__doc__ == "Retrieve user details."
    assert get.__wrapped__ is get.handler
    assert "user_id" in get.__annotations__
