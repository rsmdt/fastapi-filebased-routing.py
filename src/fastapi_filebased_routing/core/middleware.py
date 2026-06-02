"""Framework-agnostic middleware runtime.

``build_middleware_chain`` composes the ``(request, call_next)`` onion around a
handler (the first middleware in the stack becomes the outermost). The
class-based ``dispatch`` adapter lives in the sibling :mod:`.dispatch` module.

Zero framework dependencies — the chain is an ASGI-style primitive.
"""

from collections.abc import Callable, Sequence
from typing import Any


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
