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


# === Route base class and __init_subclass__ tests ===


def test_route_base_class_is_a_normal_class() -> None:
    """The Route base class itself is an ordinary class with no metaclass magic."""
    from fastapi_filebased_routing.core.middleware import Route

    assert isinstance(Route, type)
    assert Route.__name__ == "Route"
    assert type(Route) is type  # no custom metaclass


def test_subclass_is_a_real_class_with_config() -> None:
    """class GET(Route): stays a real class and exposes a RouteConfig as _config."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        @staticmethod
        async def handler(user_id: str) -> dict:
            return {"user_id": user_id}

    # GET remains a class (unlike the old metaclass, which returned a RouteConfig)
    assert isinstance(GET, type)
    assert issubclass(GET, Route)
    assert isinstance(GET._config, RouteConfig)


def test_config_is_callable_and_delegates_to_handler() -> None:
    """The built RouteConfig delegates calls to the wrapped handler."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        @staticmethod
        async def handler(user_id: str) -> dict:
            return {"user_id": user_id}

    result = asyncio.run(GET._config(user_id="123"))
    assert result == {"user_id": "123"}


def test_middleware_list_normalized_to_tuple() -> None:
    """Middleware list is normalized to tuple."""
    from fastapi_filebased_routing.core.middleware import Route

    async def auth(request: Any) -> None:
        pass

    async def rate_limit(request: Any) -> None:
        pass

    class GET(Route):
        middleware = [auth, rate_limit]

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.middleware == (auth, rate_limit)
    assert isinstance(GET._config.middleware, tuple)


def test_single_callable_middleware_normalized_to_tuple() -> None:
    """Single callable middleware is normalized to tuple of one."""
    from fastapi_filebased_routing.core.middleware import Route

    async def auth(request: Any) -> None:
        pass

    class GET(Route):
        middleware = auth

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.middleware == (auth,)
    assert isinstance(GET._config.middleware, tuple)


def test_none_middleware_normalized_to_empty_tuple() -> None:
    """None middleware is normalized to empty tuple."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        middleware = None

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.middleware == ()
    assert isinstance(GET._config.middleware, tuple)


def test_no_middleware_defaults_to_empty_tuple() -> None:
    """Missing middleware defaults to empty tuple."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.middleware == ()
    assert isinstance(GET._config.middleware, tuple)


def test_missing_handler_raises_validation_error() -> None:
    """class GET(Route): without handler raises RouteValidationError."""
    from fastapi_filebased_routing.core.middleware import Route
    from fastapi_filebased_routing.exceptions import RouteValidationError

    with pytest.raises(
        RouteValidationError,
        match=r"class GET\(Route\) must define an async def handler\(\.\.\.\) function",
    ):

        class GET(Route):
            middleware = []


def test_non_callable_handler_raises_validation_error() -> None:
    """class GET(Route): with non-callable handler raises RouteValidationError."""
    from fastapi_filebased_routing.core.middleware import Route
    from fastapi_filebased_routing.exceptions import RouteValidationError

    with pytest.raises(
        RouteValidationError,
        match=r"class GET\(Route\): handler must be a callable, got str",
    ):

        class GET(Route):
            handler = "not a function"


def test_invalid_middleware_type_raises_validation_error() -> None:
    """class GET(Route): with invalid middleware type raises RouteValidationError."""
    from fastapi_filebased_routing.core.middleware import Route
    from fastapi_filebased_routing.exceptions import RouteValidationError

    with pytest.raises(
        RouteValidationError,
        match=r"class GET\(Route\): middleware must be a list or callable, got str",
    ):

        class GET(Route):
            middleware = "invalid"

            @staticmethod
            async def handler() -> dict:
                return {}


def test_metadata_extraction_tags() -> None:
    """Metadata is extracted: tags."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        tags = ["users", "admin"]

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.tags == ("users", "admin")


def test_metadata_extraction_summary() -> None:
    """Metadata is extracted: summary."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        summary = "Get user details"

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.summary == "Get user details"


def test_metadata_extraction_deprecated() -> None:
    """Metadata is extracted: deprecated."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        deprecated = True

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.deprecated is True


def test_metadata_extraction_status_code() -> None:
    """Metadata is extracted: status_code."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        status_code = 201

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.status_code == 201


def test_full_example_with_all_features() -> None:
    """Full example: handler + middleware + metadata."""
    from fastapi_filebased_routing.core.middleware import Route

    async def auth(request: Any) -> None:
        pass

    async def rate_limit(request: Any) -> None:
        pass

    class GET(Route):
        middleware = [auth, rate_limit]
        tags = ["users"]
        summary = "Get user"
        deprecated = False
        status_code = 200

        @staticmethod
        async def handler(user_id: str) -> dict:
            return {"user_id": user_id}

    config = GET._config
    assert isinstance(config, RouteConfig)
    assert config.middleware == (auth, rate_limit)
    assert config.tags == ("users",)
    assert config.summary == "Get user"
    assert config.deprecated is False
    assert config.status_code == 200


def test_tuple_middleware_preserved() -> None:
    """Middleware as tuple is preserved."""
    from fastapi_filebased_routing.core.middleware import Route

    async def auth(request: Any) -> None:
        pass

    class GET(Route):
        middleware = (auth,)

        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.middleware == (auth,)
    assert isinstance(GET._config.middleware, tuple)


def test_deprecated_defaults_to_false() -> None:
    """deprecated defaults to False if not specified."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        @staticmethod
        async def handler() -> dict:
            return {}

    assert GET._config.deprecated is False


def test_handler_metadata_preserved() -> None:
    """Handler metadata is preserved on the RouteConfig."""
    from fastapi_filebased_routing.core.middleware import Route

    class GET(Route):
        @staticmethod
        async def handler(user_id: str) -> dict:
            """Retrieve user details."""
            return {"user_id": user_id}

    config = GET._config
    assert config.__name__ == "handler"
    assert config.__doc__ == "Retrieve user details."
    assert config.__wrapped__ is config.handler
    assert "user_id" in config.__annotations__
