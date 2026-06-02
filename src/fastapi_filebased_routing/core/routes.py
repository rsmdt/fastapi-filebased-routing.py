"""Class-based route definitions and shared definition-time middleware vocabulary.

Provides :class:`RouteConfig` (the frozen, callable config data) and the
:class:`Route` base class whose ``__init_subclass__`` validates the class body
at import time and stores the resulting config on the subclass as ``_config``.
Also owns ``normalize_middleware`` and ``validate_middleware_entries``, the
shared definition-time vocabulary used wherever middleware attributes are read.

Zero framework dependencies — depends only on the exception hierarchy.
"""

import asyncio
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi_filebased_routing.exceptions import RouteValidationError


@dataclass(frozen=True)
class RouteConfig:
    """A configured route handler with middleware and metadata.

    Built by ``Route.__init_subclass__`` when a class inherits from Route,
    and stored on the subclass as ``_config``.
    Callable — delegates to the wrapped handler function.

    Note: slots=True is omitted to allow setting special attributes
    (__wrapped__, __name__, etc.) in __post_init__ for FastAPI introspection.

    Attributes:
        handler: The actual handler function (async def or def).
        middleware: Sequence of handler-level middleware callables.
        tags: Optional OpenAPI tags override.
        summary: Optional OpenAPI summary override.
        deprecated: Whether this handler is deprecated.
        status_code: Optional HTTP status code override.
    """

    handler: Callable[..., Any]
    middleware: Sequence[Callable[..., Any]] = ()
    tags: tuple[str, ...] | None = None
    summary: str | None = None
    deprecated: bool = False
    status_code: int | None = None

    def __post_init__(self) -> None:
        """Preserve handler metadata for FastAPI introspection."""
        # functools.update_wrapper can't be used in __post_init__ of frozen dataclass
        # because it tries to set attributes. Instead, we use __wrapped__ convention.
        object.__setattr__(self, "__wrapped__", self.handler)
        object.__setattr__(self, "__name__", getattr(self.handler, "__name__", "handler"))
        object.__setattr__(self, "__doc__", getattr(self.handler, "__doc__", None))
        object.__setattr__(self, "__annotations__", getattr(self.handler, "__annotations__", {}))
        object.__setattr__(self, "__module__", getattr(self.handler, "__module__", __name__))

    def __call__(self, *args: Any, **kwargs: Any) -> Any:
        """Delegate to the wrapped handler."""
        return self.handler(*args, **kwargs)


def normalize_middleware(
    middleware_attr: Any,
    *,
    source: str = "",
) -> tuple[Callable[..., Any], ...]:
    """Normalize a middleware attribute to a tuple of callables.

    Accepts: None, single callable, list, or tuple.
    Returns: tuple of callables (empty if None).

    Args:
        middleware_attr: The middleware value to normalize.
        source: Context for error messages (e.g., "class GET(Route)").

    Raises:
        RouteValidationError: If middleware_attr is not a valid type.
    """
    if middleware_attr is None:
        return ()
    if callable(middleware_attr) and not isinstance(middleware_attr, (list, tuple)):
        return (middleware_attr,)
    if isinstance(middleware_attr, (list, tuple)):
        return tuple(middleware_attr)
    raise RouteValidationError(
        f"{source + ': ' if source else ''}middleware must be a list or callable, "
        f"got {type(middleware_attr).__name__}"
    )


def validate_middleware_entries(
    middleware: Sequence[Callable[..., Any]],
    *,
    source: str,
    error_class: type[Exception] = RouteValidationError,
) -> None:
    """Validate that all middleware entries are async callables.

    Args:
        middleware: Sequence of middleware to validate.
        source: Human-readable source for error messages (e.g., file path).
        error_class: Exception type to raise on validation failure.

    Raises:
        error_class: If any entry is not callable or not async.
    """
    for i, mw in enumerate(middleware):
        if not callable(mw):
            raise error_class(f"Non-callable middleware at index {i} in {source}")
        if not asyncio.iscoroutinefunction(mw):
            name = getattr(mw, "__name__", "unknown")
            raise error_class(
                f"Middleware at index {i} in {source} must be async, got sync function {name}"
            )


class Route:
    """Base class for configured route handlers.

    Subclass with an uppercase HTTP verb name to define a handler with
    middleware and metadata. ``__init_subclass__`` validates the class body
    at definition time and stores the resulting :class:`RouteConfig` on the
    subclass as ``_config``. Unlike the old metaclass, the subclass remains a
    real class, so static type checkers and IDEs see it honestly.

    Recognized class attributes:
        handler: The route handler (async def). Required. Use ``@staticmethod``
            to keep it lint-clean, since it takes no ``self``.
        middleware: A single callable or list/tuple of handler-level middleware.
        tags, summary, deprecated, status_code: OpenAPI metadata overrides.

    Example:
        from fastapi_filebased_routing import Route

        class GET(Route):
            middleware = [auth_required, rate_limit(100)]
            tags = ["users"]

            @staticmethod
            async def handler(user_id: str) -> dict:
                return {"user_id": user_id}

        # `GET` is a real class; `GET._config` is its RouteConfig.
    """

    _config: "RouteConfig"

    def __init_subclass__(cls, **kwargs: Any) -> None:
        """Validate the subclass body and build its RouteConfig."""
        super().__init_subclass__(**kwargs)

        handler = getattr(cls, "handler", None)

        # Validate: handler is required
        if handler is None:
            raise RouteValidationError(
                f"class {cls.__name__}(Route) must define an async def handler(...) function"
            )

        # Validate: handler must be callable
        if not callable(handler):
            raise RouteValidationError(
                f"class {cls.__name__}(Route): handler must be a callable, "
                f"got {type(handler).__name__}"
            )

        # Normalize handler-level middleware
        middleware = normalize_middleware(
            getattr(cls, "middleware", None),
            source=f"class {cls.__name__}(Route)",
        )

        # Extract metadata
        raw_tags = getattr(cls, "tags", None)
        tags = tuple(raw_tags) if raw_tags else None

        cls._config = RouteConfig(
            handler=handler,
            middleware=middleware,
            tags=tags,
            summary=getattr(cls, "summary", None),
            deprecated=bool(getattr(cls, "deprecated", False)),
            status_code=getattr(cls, "status_code", None),
        )
