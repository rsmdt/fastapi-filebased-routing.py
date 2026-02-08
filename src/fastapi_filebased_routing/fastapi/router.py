"""Router factory for file-based routing.

Composes scanner, parser, and importer to create a complete
FastAPI router from a directory structure.
"""

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from fastapi_filebased_routing.core.importer import load_route
from fastapi_filebased_routing.core.scanner import scan_routes
from fastapi_filebased_routing.exceptions import DuplicateRouteError

logger = logging.getLogger(__name__)

# Convention-based default status codes by HTTP method
DEFAULT_STATUS_CODES: dict[str, int] = {
    "post": 201,  # Created
    "delete": 204,  # No Content
}


def create_router_from_path(
    base_path: str | Path,
    *,
    prefix: str = "",
) -> APIRouter:
    """Create a FastAPI APIRouter from a directory of route.py files.

    Scans the given directory tree for route.py files, imports their HTTP
    method handlers, and registers them on a FastAPI APIRouter.

    Args:
        base_path: Root directory containing route.py files.
        prefix: Optional URL prefix for all discovered routes.

    Returns:
        A FastAPI APIRouter with all discovered routes registered.

    Raises:
        RouteDiscoveryError: If base_path doesn't exist or isn't a directory.
        RouteValidationError: If a route file has invalid exports or parameters.
        DuplicateRouteError: If two route files resolve to the same path+method.
        PathParseError: If a directory name has invalid syntax.

    Example:
        from fastapi import FastAPI
        from fastapi_filebased_routing import create_router_from_path

        app = FastAPI()
        app.include_router(create_router_from_path("app"))
    """
    base = Path(base_path).resolve()

    # Scan for all route definitions
    route_defs = scan_routes(base)

    logger.info(
        "Discovered route files",
        extra={"count": len(route_defs), "base_path": str(base)},
    )

    # Track registered routes to detect duplicates
    registered: dict[tuple[str, str], Path] = {}  # (path, method) -> file

    # Create the main router
    router = APIRouter(prefix=prefix)

    # Sort routes for priority: static before dynamic, shorter before longer
    sorted_routes = sorted(
        route_defs,
        key=lambda r: (
            # Static routes first (fewer parameters)
            len([s for s in r.segments if s.is_parameter]),
            # Shorter paths first
            len(r.segments),
            # Alphabetical for consistency
            r.path,
        ),
    )

    for route_def in sorted_routes:
        # Load handlers from the route file
        extracted = load_route(route_def.file_path, base_path=base)

        # Skip route files with no handlers
        if not extracted.handlers:
            continue

        # Determine tags from metadata or derive from path
        tags = extracted.metadata.tags or _derive_tags(route_def.path)

        # Register each handler
        for method, handler in extracted.handlers.items():
            route_key = (route_def.path, method.upper())

            # Check for duplicates
            if route_key in registered:
                raise DuplicateRouteError(
                    f"Duplicate route: {method.upper()} {route_def.path}\n"
                    f"  First: {registered[route_key]}\n"
                    f"  Second: {route_def.file_path}"
                )
            registered[route_key] = route_def.file_path

            # Handle WebSocket vs HTTP methods differently
            if method == "websocket":
                # WebSocket registration
                router.websocket(route_def.path)(handler)
            else:
                # HTTP method registration
                # Apply convention-based status code defaults
                status_code = DEFAULT_STATUS_CODES.get(method)

                # Add route to the router
                _add_route(
                    router=router,
                    path=route_def.path,
                    method=method,
                    handler=handler,
                    tags=tags,
                    summary=extracted.metadata.summary,
                    deprecated=extracted.metadata.deprecated,
                    status_code=status_code,
                )

            logger.debug(
                "Registered route",
                extra={
                    "method": method.upper(),
                    "path": route_def.path,
                    "file": str(route_def.file_path),
                },
            )

    logger.info(
        "Route registration complete",
        extra={
            "route_count": len(registered),
            "prefix": prefix or "(none)",
        },
    )

    return router


def _add_route(
    router: APIRouter,
    path: str,
    method: str,
    handler: Callable[..., Any],
    tags: list[str],
    deprecated: bool,
    summary: str | None = None,
    status_code: int | None = None,
) -> None:
    """Add an HTTP route to the router with metadata.

    Args:
        router: The APIRouter to add the route to.
        path: The URL path for the route.
        method: The HTTP method (lowercase).
        handler: The handler function.
        tags: List of OpenAPI tags.
        deprecated: Whether the route is deprecated.
        summary: Optional OpenAPI summary.
        status_code: Optional HTTP status code override.
    """
    # Map method name to router decorator
    add_method = getattr(router, method.lower())

    # Extract docstring for OpenAPI description
    description = handler.__doc__

    # Build kwargs for route registration
    kwargs: dict[str, Any] = {
        "tags": tags,
        "deprecated": deprecated,
        "description": description,
    }

    # Add summary if provided
    if summary is not None:
        kwargs["summary"] = summary

    # Add status code if specified
    if status_code is not None:
        kwargs["status_code"] = status_code

    add_method(path, **kwargs)(handler)


def _derive_tags(path: str) -> list[str]:
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
