"""Router factory for file-based routing.

Composes scanner, parser, and importer to create a complete
FastAPI router from a directory structure.
"""

import asyncio
import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from fastapi.routing import APIRoute

from fastapi_filebased_routing.core.importer import _import_module_from_file, load_route
from fastapi_filebased_routing.core.middleware import (
    RouteConfig,
    build_middleware_chain,
    normalize_middleware,
)
from fastapi_filebased_routing.core.scanner import MiddlewareFile, scan_middleware, scan_routes
from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    MiddlewareValidationError,
)

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

    # Scan for middleware files
    middleware_files = scan_middleware(base)

    # Import and validate all middleware files
    dir_middleware = _load_directory_middleware(middleware_files, base)

    logger.info(
        "Discovered middleware files",
        extra={"count": len(middleware_files), "base_path": str(base)},
    )

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

    # Register all route handlers
    registered = _register_route_handlers(router, sorted_routes, base, dir_middleware)

    logger.info(
        "Route registration complete",
        extra={
            "route_count": len(registered),
            "prefix": prefix or "(none)",
        },
    )

    return router


def _register_route_handlers(  # noqa: C901
    router: APIRouter,
    sorted_routes: list[Any],
    base_path: Path,
    dir_middleware: dict[Path, tuple[Callable[..., Any], ...]],
) -> dict[tuple[str, str], Path]:
    """Register all route handlers on the router.

    Iterates over sorted route definitions, loads handlers, applies middleware,
    and registers them on the router.

    Args:
        router: The APIRouter to register routes on.
        sorted_routes: Route definitions sorted by priority.
        base_path: Base directory of the route tree.
        dir_middleware: Dictionary mapping directory paths to middleware tuples.

    Returns:
        Dictionary of registered (path, method) -> file_path for duplicate detection.

    Raises:
        DuplicateRouteError: If two route files resolve to the same path+method.
    """
    registered: dict[tuple[str, str], Path] = {}

    for route_def in sorted_routes:
        # Load handlers from the route file
        extracted = load_route(route_def.file_path, base_path=base_path)

        # Skip route files with no handlers
        if not extracted.handlers:
            continue

        # Collect applicable directory middleware for this route
        route_dir = route_def.file_path.parent
        applicable_dir_mw = _collect_directory_middleware(
            route_dir=route_dir,
            base_path=base_path,
            dir_middleware=dir_middleware,
        )

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

            # Extract handler function and handler-level middleware
            handler_mw: tuple[Callable[..., Any], ...] = ()
            handler_fn = handler
            handler_tags = tags
            handler_summary = extracted.metadata.summary
            handler_deprecated = extracted.metadata.deprecated
            handler_status_code = DEFAULT_STATUS_CODES.get(method)

            # Check if handler is a RouteConfig
            if isinstance(handler, RouteConfig):
                handler_mw = tuple(handler.middleware)
                handler_fn = handler.handler

                # Override metadata if RouteConfig provides non-None values
                if handler.tags is not None:
                    handler_tags = list(handler.tags)
                if handler.summary is not None:
                    handler_summary = handler.summary
                handler_deprecated = handler.deprecated
                if handler.status_code is not None:
                    handler_status_code = handler.status_code

            # Handle WebSocket vs HTTP methods differently
            if method == "websocket":
                # Warn if middleware would apply but gets skipped
                applicable_mw = (*applicable_dir_mw, *extracted.file_middleware, *handler_mw)
                if applicable_mw:
                    logger.warning(
                        "WebSocket handler has applicable middleware that will be skipped. "
                        "WebSocket middleware is not yet supported.",
                        extra={
                            "path": route_def.path,
                            "skipped_middleware_count": len(applicable_mw),
                        },
                    )
                # WebSocket registration
                router.websocket(route_def.path)(handler_fn)
            else:
                # Assemble full middleware stack
                # Order: directory (root→leaf) + file-level + handler-level
                full_middleware = (
                    *applicable_dir_mw,
                    *extracted.file_middleware,
                    *handler_mw,
                )

                # Create custom APIRoute subclass if middleware exists
                route_class = None
                if full_middleware:
                    route_class = _make_middleware_route(full_middleware)
                    logger.debug(
                        "Created middleware route class",
                        extra={
                            "method": method.upper(),
                            "path": route_def.path,
                            "middleware_count": len(full_middleware),
                        },
                    )

                # Add route to the router
                _add_route(
                    router=router,
                    path=route_def.path,
                    method=method,
                    handler=handler_fn,
                    tags=handler_tags,
                    summary=handler_summary,
                    deprecated=handler_deprecated,
                    status_code=handler_status_code,
                    route_class=route_class,
                )

            logger.debug(
                "Registered route",
                extra={
                    "method": method.upper(),
                    "path": route_def.path,
                    "file": str(route_def.file_path),
                },
            )

    return registered


def _add_route(
    router: APIRouter,
    path: str,
    method: str,
    handler: Callable[..., Any],
    tags: list[str],
    deprecated: bool,
    summary: str | None = None,
    status_code: int | None = None,
    route_class: type[APIRoute] | None = None,
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
        route_class: Optional custom APIRoute subclass for middleware wrapping.
    """
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

    # Add custom route class if provided
    if route_class is not None:
        kwargs["route_class_override"] = route_class

    # Use add_api_route for direct registration with custom route class
    router.add_api_route(
        path=path,
        endpoint=handler,
        methods=[method.upper()],
        **kwargs,
    )


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


def _import_middleware_module(file_path: Path, base_path: Path) -> Any:
    """Import a _middleware.py module dynamically.

    Args:
        file_path: Path to the _middleware.py file.
        base_path: Base directory for module name generation.

    Returns:
        The imported module.

    Raises:
        MiddlewareValidationError: If import fails.
    """
    # Generate a unique module name to avoid conflicts
    try:
        rel_path = file_path.relative_to(base_path)
    except ValueError:
        rel_path = file_path

    module_name = f"_middleware_{rel_path.parent}".replace("/", ".").replace("\\", ".")

    try:
        return _import_module_from_file(file_path, module_name)
    except Exception as exc:
        raise MiddlewareValidationError(f"Failed to import {file_path}: {exc}") from exc


def _load_directory_middleware(
    middleware_files: list[MiddlewareFile],
    base_path: Path,
) -> dict[Path, tuple[Callable[..., Any], ...]]:
    """Import _middleware.py files and extract their middleware callables.

    Returns a dict mapping directory path to its middleware tuple.
    Validates all middleware are async callables.

    Args:
        middleware_files: List of MiddlewareFile objects to import.
        base_path: Base directory for module import.

    Returns:
        Dictionary mapping directory Path to tuple of middleware callables.

    Raises:
        MiddlewareValidationError: If import fails, middleware is invalid,
            or middleware is not async.
    """
    result: dict[Path, tuple[Callable[..., Any], ...]] = {}

    for mw_file in middleware_files:
        # Import the module
        module = _import_middleware_module(mw_file.file_path, base_path)

        # Extract middleware attribute
        mw_attr = getattr(module, "middleware", None)

        # Handle inline single function: module has async def middleware(request, call_next)
        # In this case mw_attr IS the function
        if mw_attr is None:
            continue  # No middleware in this file

        # Normalize
        try:
            middleware_list = list(
                normalize_middleware(
                    mw_attr,
                    source=f"_middleware.py in {mw_file.file_path.parent}",
                )
            )
        except Exception as exc:
            raise MiddlewareValidationError(
                f"middleware attribute in {mw_file.file_path} must be a list or callable, "
                f"got {type(mw_attr).__name__}"
            ) from exc

        # Validate each middleware
        for i, mw in enumerate(middleware_list):
            if not callable(mw):
                raise MiddlewareValidationError(
                    f"Non-callable middleware at index {i} in {mw_file.file_path}"
                )
            if not asyncio.iscoroutinefunction(mw):
                raise MiddlewareValidationError(
                    f"Middleware at index {i} in {mw_file.file_path} must be async, "
                    f"got sync function {mw.__name__}"
                )

        result[mw_file.directory] = tuple(middleware_list)

    return result


def _collect_directory_middleware(
    route_dir: Path,
    base_path: Path,
    dir_middleware: dict[Path, tuple[Callable[..., Any], ...]],
) -> tuple[Callable[..., Any], ...]:
    """Collect middleware applicable to a route directory.

    Walks from base_path to route_dir, collecting middleware from
    each directory that has loaded middleware. Order: parent before child.

    Args:
        route_dir: Directory containing the route file.
        base_path: Base directory of the route tree.
        dir_middleware: Dictionary mapping directory paths to their middleware.

    Returns:
        Tuple of middleware callables in parent-before-child order.
    """
    # Walk from base_path to route_dir
    middleware: list[Callable[..., Any]] = []

    # Check base_path itself
    if base_path in dir_middleware:
        middleware.extend(dir_middleware[base_path])

    # Walk each directory from base to route_dir
    try:
        rel_path = route_dir.relative_to(base_path)
    except ValueError:
        return tuple(middleware)

    current = base_path
    for part in rel_path.parts:
        current = current / part
        if current in dir_middleware:
            middleware.extend(dir_middleware[current])

    return tuple(middleware)


def _make_middleware_route(
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
