"""Thin orchestration for building a FastAPI router from a directory tree.

``create_router_from_path`` is the sole entry point. It sequences the pipeline
(validate filters -> scan -> select -> load directory middleware -> create
router -> sort -> register with duplicate detection) and delegates every step;
it contains no registration bodies, APIRoute subclass, tag derivation, or
middleware-loading logic.
"""

import logging
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from fastapi_filebased_routing.adapter.registration import (
    derive_tags,
    register_http_route,
    register_websocket_route,
    resolve_handler,
)
from fastapi_filebased_routing.core.discovery import scan_directory_middleware, scan_routes
from fastapi_filebased_routing.core.handlers import load_route
from fastapi_filebased_routing.core.middleware_loader import (
    collect_directory_middleware,
    load_directory_middleware,
)
from fastapi_filebased_routing.core.selection import (
    compute_active_directories,
    filter_directory_middleware,
    filter_routes,
    validate_filter_params,
)
from fastapi_filebased_routing.exceptions import DuplicateRouteError

logger = logging.getLogger(__name__)


def create_router_from_path(
    base_path: str | Path,
    *,
    prefix: str = "",
    include: Sequence[str] | None = None,
    exclude: Sequence[str] | None = None,
) -> APIRouter:
    """Create a FastAPI APIRouter from a directory of route.py files.

    Scans the given directory tree for route.py files, imports their HTTP
    method handlers, and registers them on a FastAPI APIRouter.

    Args:
        base_path: Root directory containing route.py files.
        prefix: Optional URL prefix for all discovered routes.
        include: Allowlist of route patterns. Only matching routes are loaded.
            Patterns can be bare names (segment-level) or glob patterns.
        exclude: Denylist of route patterns. Matching routes are skipped.
            Patterns can be bare names (segment-level) or glob patterns.

    Returns:
        A FastAPI APIRouter with all discovered routes registered.

    Raises:
        RouteDiscoveryError: If base_path doesn't exist or isn't a directory.
        RouteValidationError: If a route file has invalid exports or parameters.
        DuplicateRouteError: If two route files resolve to the same path+method.
        PathParseError: If a directory name has invalid syntax.
        RouteFilterError: If both include and exclude are provided.

    Example:
        from fastapi import FastAPI
        from fastapi_filebased_routing import create_router_from_path

        app = FastAPI()
        app.include_router(create_router_from_path("app"))

        # DMZ deployment: only public routes
        app.include_router(create_router_from_path("app", include=["(public)"]))

        # Internal: everything except public
        app.include_router(create_router_from_path("app", exclude=["(public)"]))
    """
    # Fail fast if both include and exclude are provided
    validate_filter_params(include, exclude)

    base = Path(base_path).resolve()

    # Scan for all route definitions, then filter before any imports
    route_defs = scan_routes(base)
    route_defs = filter_routes(route_defs, base_path=base, include=include, exclude=exclude)

    logger.info(
        "Discovered route files",
        extra={"count": len(route_defs), "base_path": str(base)},
    )

    # Scan for directory middleware, pruning to ancestors of surviving routes
    dir_middleware_files = scan_directory_middleware(base)
    if include or exclude:
        active_dirs = compute_active_directories(route_defs, base)
        dir_middleware_files = filter_directory_middleware(dir_middleware_files, active_dirs)

    # Import and validate all directory middleware
    dir_middleware = load_directory_middleware(dir_middleware_files, base)

    logger.info(
        "Discovered middleware files",
        extra={"count": len(dir_middleware_files), "base_path": str(base)},
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

    # Register all route handlers (duplicate detection inlined here)
    registered: dict[tuple[str, str], Path] = {}

    for route_def in sorted_routes:
        extracted = load_route(route_def.file_path, base_path=base)
        if not extracted.handlers:
            continue

        applicable_dir_mw = collect_directory_middleware(
            route_dir=route_def.file_path.parent,
            base_path=base,
            dir_middleware=dir_middleware,
        )
        tags = extracted.metadata.tags or derive_tags(route_def.path)

        for method, handler in extracted.handlers.items():
            route_key = (route_def.path, method.upper())
            if route_key in registered:
                raise DuplicateRouteError(
                    f"Duplicate route: {method.upper()} {route_def.path}\n"
                    f"  First: {registered[route_key]}\n"
                    f"  Second: {route_def.file_path}"
                )
            registered[route_key] = route_def.file_path

            resolved = resolve_handler(
                handler,
                method,
                tags,
                extracted.metadata.summary,
                extracted.metadata.deprecated,
            )

            full_middleware: tuple[Callable[..., Any], ...] = (
                *applicable_dir_mw,
                *extracted.file_middleware,
                *resolved.middleware,
            )

            if method == "websocket":
                register_websocket_route(router, route_def.path, resolved.handler, full_middleware)
            else:
                register_http_route(router, route_def.path, method, resolved, full_middleware)

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
