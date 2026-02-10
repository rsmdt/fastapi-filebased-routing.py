"""Middleware primitives for file-based routing.

Provides RouteConfig, the route metaclass, and middleware chain assembly.
Zero framework dependencies — works with any ASGI-compatible middleware.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi_filebased_routing.exceptions import RouteValidationError


@dataclass(frozen=True)
class RouteConfig:
    """A configured route handler with middleware and metadata.

    Created by the _RouteMeta metaclass when a class inherits from route.
    Callable — delegates to the wrapped handler function.

    Note: slots=True is omitted to allow setting special attributes
    (__wrapped__, __name__, etc.) in __post_init__ for FastAPI introspection.

    Attributes:
        handler: The actual handler function (async def or def).
        middleware: Sequence of middleware callables.
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
        source: Context for error messages (e.g., "class get(route)").

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


class _RouteMeta(type):
    """Metaclass that intercepts class body and returns RouteConfig.

    When a class inherits from `route`, this metaclass:
    1. Extracts `handler` function from the class body
    2. Extracts `middleware` (list or single callable) from the class body
    3. Extracts metadata (tags, summary, deprecated, status_code)
    4. Returns a RouteConfig instance instead of a class

    This means `class get(route): ...` produces a RouteConfig, not a class.
    """

    def __new__(
        mcs,
        name: str,
        bases: tuple[type, ...],
        namespace: dict[str, Any],
    ) -> Any:  # Returns RouteConfig, not type — intentional
        """Create a new class or return RouteConfig based on inheritance."""
        # The `route` base class itself — create normally
        if not bases:
            return super().__new__(mcs, name, bases, namespace)

        # Subclass of route → intercept and return RouteConfig
        handler = namespace.get("handler")
        middleware_attr = namespace.get("middleware")

        # Validate: handler is required
        if handler is None:
            raise RouteValidationError(
                f"class {name}(route) must define an async def handler(...) function"
            )

        # Validate: handler must be callable
        if not callable(handler):
            raise RouteValidationError(
                f"class {name}(route): handler must be a callable, got {type(handler).__name__}"
            )

        # Normalize middleware
        middleware = normalize_middleware(
            middleware_attr,
            source=f"class {name}(route)",
        )

        # Extract metadata
        raw_tags = namespace.get("tags")
        tags = tuple(raw_tags) if raw_tags else None
        summary = namespace.get("summary")
        deprecated = namespace.get("deprecated", False)
        status_code = namespace.get("status_code")

        return RouteConfig(
            handler=handler,
            middleware=middleware,
            tags=tags,
            summary=summary,
            deprecated=bool(deprecated),
            status_code=status_code,
        )


class route(metaclass=_RouteMeta):  # noqa: N801
    """Base class for configured route handlers.

    Use `class handler_name(route):` to define a handler with middleware
    and metadata. The metaclass intercepts the class body and returns a
    RouteConfig instead of a class.

    Example:
        from fastapi_filebased_routing import route

        class get(route):
            middleware = [auth_required, rate_limit(100)]
            tags = ["users"]

            async def handler(user_id: str) -> dict:
                return {"user_id": user_id}

        # `get` is now a RouteConfig, not a class
        # `get(user_id="123")` calls the handler directly
    """


def build_middleware_chain(
    handler: Callable[..., Any],
    middleware_stack: Sequence[Callable[..., Any]],
) -> Callable[..., Any]:
    """Wrap a handler function with a middleware chain.

    Composes middleware in order so that the first middleware in the list
    is the outermost (executes first). Each middleware receives (request, call_next)
    where call_next invokes the next middleware or handler.

    Args:
        handler: The route handler function.
        middleware_stack: Ordered sequence of middleware (outermost first).

    Returns:
        A wrapped handler function that executes the middleware chain.
        If middleware_stack is empty, returns the handler unchanged.
    """
    if not middleware_stack:
        return handler

    # Build chain from inside out (last middleware wraps handler first)
    chain = handler
    for mw in reversed(middleware_stack):
        chain = _wrap_with_middleware(chain, mw)
    return chain


async def _noop_app(scope: Any, receive: Any, send: Any) -> None:
    """Placeholder ASGI app for class-based middleware adaptation."""


def dispatch(cls: type, **kwargs: Any) -> Callable[..., Any]:
    """Adapt a class-based middleware for use in _middleware.py.

    Lazily instantiates the class on first request and delegates to its
    dispatch method. The class must accept ``app`` as its first constructor
    argument and expose an async ``dispatch(request, call_next)`` method.

    Args:
        cls: Middleware class (e.g. a BaseHTTPMiddleware subclass).
        **kwargs: Arguments forwarded to ``cls.__init__`` (after app).

    Returns:
        An async middleware function compatible with the middleware pipeline.
    """
    instance: object | None = None

    async def middleware(request: Any, call_next: Any) -> Any:
        nonlocal instance
        if instance is None:
            instance = cls(app=_noop_app, **kwargs)
        return await instance.dispatch(request, call_next)  # type: ignore[union-attr]

    middleware.__name__ = f"dispatch({cls.__name__})"
    middleware.__qualname__ = middleware.__name__
    return middleware


def _wrap_with_middleware(
    next_handler: Callable[..., Any],
    middleware: Callable[..., Any],
) -> Callable[..., Any]:
    """Wrap a handler with a single middleware function.

    Args:
        next_handler: The next function in the chain (middleware or handler).
        middleware: The middleware function with signature (request, call_next).

    Returns:
        A new async function that calls middleware(request, call_next).
    """

    async def wrapped(request: Any) -> Any:
        async def call_next(req: Any) -> Any:
            return await next_handler(req)

        return await middleware(request, call_next)

    # Preserve metadata for debugging
    wrapped.__name__ = (
        f"{middleware.__name__}_wrapping_{getattr(next_handler, '__name__', 'handler')}"
    )
    wrapped.__qualname__ = wrapped.__name__

    return wrapped
