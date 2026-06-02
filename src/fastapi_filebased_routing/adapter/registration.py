"""FastAPI-specific route registration.

The single place that touches ``APIRouter`` / ``APIRoute``. Owns the default
status-code conventions, the :class:`ResolvedHandler` result, handler resolution
(unwrapping RouteConfig and applying metadata/status defaults), tag derivation,
HTTP and WebSocket registration, and the custom middleware-wrapping APIRoute
factory.

The term "handler" is used for the user's callable throughout; FastAPI's
``endpoint=`` keyword appears only at the literal ``add_api_route`` call site.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute

from fastapi_filebased_routing.core.middleware import build_middleware_chain
from fastapi_filebased_routing.core.routes import RouteConfig

logger = logging.getLogger(__name__)

# Convention-based default status codes by HTTP method
DEFAULT_STATUS_CODES: dict[str, int] = {
    "post": 201,  # Created
    "delete": 204,  # No Content
}


@dataclass(frozen=True)
class ResolvedHandler:
    """A handler resolved into its callable, middleware, and metadata.

    Produced by :func:`resolve_handler` after unwrapping any RouteConfig and
    applying metadata and status-code defaults.

    Attributes:
        handler: The handler callable to register.
        middleware: Handler-level middleware tuple.
        tags: OpenAPI tags for the route.
        summary: OpenAPI summary, or None.
        deprecated: Whether the route is deprecated.
        status_code: HTTP status code override, or None to use FastAPI's default.
    """

    handler: Callable[..., Any]
    middleware: tuple[Callable[..., Any], ...]
    tags: list[str]
    summary: str | None
    deprecated: bool
    status_code: int | None


def resolve_handler(
    handler: Any,
    method: str,
    default_tags: list[str],
    default_summary: str | None,
    default_deprecated: bool,
) -> ResolvedHandler:
    """Resolve a handler into its callable, middleware, and metadata.

    Unwraps RouteConfig instances and applies metadata defaults. The
    None-vs-explicit status_code distinction is preserved: when no convention
    default and no override apply, status_code stays None so it never reaches
    ``add_api_route``.

    Args:
        handler: The handler function or RouteConfig.
        method: HTTP method name (for default status code lookup).
        default_tags: Default tags from route metadata.
        default_summary: Default summary from route metadata.
        default_deprecated: Default deprecated flag from route metadata.

    Returns:
        A ResolvedHandler with named fields.
    """
    handler_mw: tuple[Callable[..., Any], ...] = ()
    handler_fn = handler
    resolved_tags = default_tags
    resolved_summary = default_summary
    resolved_deprecated = default_deprecated
    resolved_status_code = DEFAULT_STATUS_CODES.get(method)

    if isinstance(handler, RouteConfig):
        handler_mw = tuple(handler.middleware)
        handler_fn = handler.handler
        if handler.tags is not None:
            resolved_tags = list(handler.tags)
        if handler.summary is not None:
            resolved_summary = handler.summary
        resolved_deprecated = handler.deprecated
        if handler.status_code is not None:
            resolved_status_code = handler.status_code

    return ResolvedHandler(
        handler=handler_fn,
        middleware=handler_mw,
        tags=resolved_tags,
        summary=resolved_summary,
        deprecated=resolved_deprecated,
        status_code=resolved_status_code,
    )


def derive_tags(path: str) -> list[str]:
    """Derive OpenAPI tags from a URL path.

    Takes the first non-parameter, non-group segment from the path.

    Args:
        path: FastAPI-style path string (e.g., /users/{id}, /api/{version}/users).

    Returns:
        List containing a single tag derived from the path, or ["root"] if
        only parameters/groups exist.

    Examples:
        /users/{id} -> ["users"]
        /api/{version}/users -> ["api"]
        /{id} -> ["root"]
        / -> ["root"]
    """
    # Split path and filter out empty strings and parameters
    parts = [p for p in path.split("/") if p and not p.startswith("{")]

    if parts:
        # Take the first meaningful segment
        return [parts[0]]
    else:
        # Only parameters or root path
        return ["root"]


def register_websocket_route(
    router: APIRouter,
    path: str,
    handler: Callable[..., Any],
    all_middleware: tuple[Callable[..., Any], ...],
) -> None:
    """Register a WebSocket handler, warning if middleware would be skipped.

    Args:
        router: The APIRouter to register on.
        path: The URL path for the WebSocket route.
        handler: The WebSocket handler function.
        all_middleware: Combined middleware that would apply (for warning only).
    """
    if all_middleware:
        logger.warning(
            "WebSocket handler has applicable middleware that will be skipped. "
            "WebSocket middleware is not yet supported.",
            extra={
                "path": path,
                "skipped_middleware_count": len(all_middleware),
            },
        )
    router.websocket(path)(handler)


def register_http_route(
    router: APIRouter,
    path: str,
    method: str,
    resolved: ResolvedHandler,
    full_middleware: tuple[Callable[..., Any], ...],
) -> None:
    """Register an HTTP handler with optional middleware wrapping.

    Args:
        router: The APIRouter to register on.
        path: The URL path for the route.
        method: HTTP method name (lowercase).
        resolved: The resolved handler, carrying its callable and metadata.
        full_middleware: Combined middleware stack (directory + file + handler).
    """
    route_class = None
    if full_middleware:
        route_class = make_middleware_route(full_middleware)
        logger.debug(
            "Created middleware route class",
            extra={
                "method": method.upper(),
                "path": path,
                "middleware_count": len(full_middleware),
            },
        )

    # Build kwargs for route registration (docstring becomes the OpenAPI description)
    kwargs: dict[str, Any] = {
        "tags": resolved.tags,
        "deprecated": resolved.deprecated,
        "description": resolved.handler.__doc__,
    }

    # Add summary if provided
    if resolved.summary is not None:
        kwargs["summary"] = resolved.summary

    # Add status code if specified
    if resolved.status_code is not None:
        kwargs["status_code"] = resolved.status_code

    # Add custom route class if provided
    if route_class is not None:
        kwargs["route_class_override"] = route_class

    # Use add_api_route for direct registration with custom route class.
    # This is the single boundary where FastAPI's endpoint= kwarg is used.
    router.add_api_route(
        path=path,
        endpoint=resolved.handler,
        methods=[method.upper()],
        **kwargs,
    )


def make_middleware_route(
    middleware_stack: Sequence[Callable[..., Any]],
) -> type[APIRoute]:
    """Create a custom APIRoute subclass that wraps handlers with middleware.

    The wrapping happens in get_route_handler(), called AFTER FastAPI resolves
    dependency injection. This means middleware receives (request, call_next)
    where the handler has already had its path params, query params, etc. resolved.

    Args:
        middleware_stack: Ordered sequence of middleware (outermost first).

    Returns:
        A subclass of APIRoute with middleware wrapping.
    """

    class MiddlewareRoute(APIRoute):
        def get_route_handler(self) -> Callable[..., Any]:
            original_handler = super().get_route_handler()
            return build_middleware_chain(original_handler, middleware_stack)

    return MiddlewareRoute
