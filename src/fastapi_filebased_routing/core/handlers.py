"""High-level route.py interpretation for file-based routing.

Given a ``route.py`` path, loads it via the module loader, then extracts the
verb->handler map (plain async functions AND ``class VERB(Route)`` -> RouteConfig),
RouteMetadata (TAGS/SUMMARY/DEPRECATED), and file-level middleware. Enforces the
allowed-export rules and the async-websocket rule.

``load_route`` is the single public entry point. Route subclasses are detected
by isinstance before the uppercase-constant skip, so verb names like GET/POST
are treated as handlers rather than module constants.
"""

import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from fastapi_filebased_routing.core.module_loader import import_route_module
from fastapi_filebased_routing.core.routes import (
    Route,
    normalize_middleware,
    validate_middleware_entries,
)
from fastapi_filebased_routing.exceptions import RouteValidationError

# HTTP methods and WebSocket that can be exported from route.py files
ALLOWED_HANDLERS: frozenset[str] = frozenset(
    {
        "get",
        "post",
        "put",
        "patch",
        "delete",
        "head",
        "options",
        "websocket",
    }
)


@dataclass(frozen=True)
class RouteMetadata:
    """Metadata extracted from a route module's constants.

    Attributes:
        tags: List of OpenAPI tags for the route.
        summary: OpenAPI summary for the route.
        deprecated: Whether the route is deprecated.
    """

    tags: list[str] | None = None
    summary: str | None = None
    deprecated: bool = False


@dataclass(frozen=True)
class ExtractedRoute:
    """Handlers and metadata extracted from a route.py module.

    Attributes:
        handlers: Dictionary mapping HTTP method names to handler functions.
        metadata: Route metadata (tags, summary, deprecated).
        file_middleware: File-level middleware extracted from the module-level
            ``middleware`` attribute (non-cascading).
    """

    handlers: dict[str, Callable[..., Any]]
    metadata: RouteMetadata
    file_middleware: Sequence[Callable[..., Any]] = ()


def _ensure_websocket_async(handler_fn: Callable[..., Any], file_path: Path) -> None:
    """Validate that a websocket handler is an async coroutine function.

    Args:
        handler_fn: The websocket handler callable.
        file_path: Path to the route file (for error messages).

    Raises:
        RouteValidationError: If the handler is not a coroutine function.
    """
    if not inspect.iscoroutinefunction(handler_fn):
        raise RouteValidationError(
            f"WebSocket handler must be async in route.py\n"
            f"  File: {file_path}\n"
            f"  Hint: Define the websocket handler with 'async def'."
        )


def _extract_metadata(module: ModuleType) -> RouteMetadata:
    """Read the TAGS/SUMMARY/DEPRECATED module constants into RouteMetadata."""
    tags = getattr(module, "TAGS", None)
    return RouteMetadata(
        tags=list(tags) if tags else None,
        summary=getattr(module, "SUMMARY", None),
        deprecated=bool(getattr(module, "DEPRECATED", False)),
    )


def _is_non_handler_member(
    name: str,
    obj: Any,
    module: ModuleType,
    middleware_names: set[str],
) -> bool:
    """Return True for module members that are not route handlers.

    Filters out uppercase constants, the ``middleware`` attribute, non-callables,
    imported callables (defined elsewhere), and the file-middleware functions.
    """
    return (
        name.isupper()
        or name == "middleware"
        or not callable(obj)
        or (hasattr(obj, "__module__") and obj.__module__ != module.__name__)
        or name in middleware_names
    )


def _record_handler(
    name: str,
    handler: Callable[..., Any],
    websocket_target: Callable[..., Any],
    file_path: Path,
    handlers: dict[str, Callable[..., Any]],
    invalid_exports: list[str],
) -> None:
    """Register ``handler`` under its verb, or flag ``name`` as an invalid export.

    ``websocket_target`` is the callable checked for async-ness when the verb is
    ``websocket`` (the underlying handler, which differs from ``handler`` when
    the handler is a RouteConfig).
    """
    if name.lower() not in ALLOWED_HANDLERS:
        invalid_exports.append(name)
        return
    verb = name.lower()
    if verb == "websocket":
        _ensure_websocket_async(websocket_target, file_path)
    handlers[verb] = handler


def _extract_handlers(module: ModuleType, file_path: Path) -> ExtractedRoute:
    """Extract HTTP method handlers and metadata from a route module.

    Args:
        module: The imported route module.
        file_path: Path to the route file (for error messages).

    Returns:
        ExtractedRoute containing handlers and metadata.

    Raises:
        RouteValidationError: If invalid exports are found or WebSocket
            handler is not async.
    """
    metadata = _extract_metadata(module)

    # Extract and validate file-level middleware (module-level, non-cascading)
    file_middleware = normalize_middleware(
        getattr(module, "middleware", None),
        source=f"file {file_path}",
    )
    validate_middleware_entries(file_middleware, source=str(file_path))

    # Middleware function names are skipped during handler detection below
    middleware_names = {mw.__name__ for mw in file_middleware if hasattr(mw, "__name__")}

    handlers: dict[str, Callable[..., Any]] = {}
    invalid_exports: list[str] = []

    for name in dir(module):
        # Skip dunders and underscore-prefixed private helpers
        if name.startswith("_"):
            continue

        obj = getattr(module, name)

        # Route subclass (class GET(Route)) → register its built RouteConfig.
        # Checked before _is_non_handler_member: verb names like GET/POST are
        # all-caps and would otherwise be filtered out as uppercase constants.
        if isinstance(obj, type) and issubclass(obj, Route) and obj is not Route:
            _record_handler(
                name, obj._config, obj._config.handler, file_path, handlers, invalid_exports
            )
            continue

        if _is_non_handler_member(name, obj, module, middleware_names):
            continue

        # A plain public callable: a verb handler, or an invalid export
        _record_handler(name, obj, obj, file_path, handlers, invalid_exports)

    # Fail fast on invalid exports
    if invalid_exports:
        raise RouteValidationError(
            f"Invalid export(s) {invalid_exports} in route.py\n"
            f"  File: {file_path}\n"
            f"  Hint: Only HTTP verbs ({', '.join(sorted(ALLOWED_HANDLERS))}) are allowed.\n"
            f"        Prefix helper functions with underscore: _{invalid_exports[0]}"
        )

    return ExtractedRoute(handlers=handlers, metadata=metadata, file_middleware=file_middleware)


def load_route(file_path: Path, *, base_path: Path | None = None) -> ExtractedRoute:
    """Import a route.py file and extract its handlers.

    Single public entry for route interpretation: loads the module via the
    module loader, then extracts verb handlers, metadata, and file middleware.

    Args:
        file_path: Path to the route.py file.
        base_path: Optional base directory to restrict imports to.

    Returns:
        ExtractedRoute containing handlers and metadata.

    Raises:
        RouteValidationError: If the path is invalid, import fails,
            or handlers are invalid.
    """
    module = import_route_module(file_path, base_path=base_path)
    return _extract_handlers(module, file_path)
