"""Adapter for class-based middleware.

``dispatch`` turns a class-based middleware (constructed with ``app=...`` and
exposing an async ``dispatch(request, call_next)`` method) into the plain
``(request, call_next)`` callable shape used everywhere else in the pipeline.

Zero framework dependencies — the adapted callable is an ASGI-style primitive.
"""

from collections.abc import Callable
from typing import Any


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
