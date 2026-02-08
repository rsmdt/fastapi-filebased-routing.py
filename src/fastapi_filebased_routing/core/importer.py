"""Module importer for file-based routing.

Dynamically imports route.py modules and extracts HTTP method handlers.
Validates that only allowed exports (HTTP verbs) are present.
"""

import asyncio
import importlib.util
import inspect
import re
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any

from fastapi_filebased_routing.core.middleware import RouteConfig, normalize_middleware
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

# Valid Python identifier pattern (alphanumeric + underscore, not starting with digit)
_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# File identity cache: maps (st_dev, st_ino) to module_name for symlink detection
_file_identity_cache: dict[tuple[int, int], str] = {}


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
        file_middleware: File-level middleware extracted from module-level middleware attribute.
    """

    handlers: dict[str, Callable[..., Any]]
    metadata: RouteMetadata
    file_middleware: Sequence[Callable[..., Any]] = ()


def _validate_parameter_name(param: str, segment: str) -> None:
    """Validate that a parameter name is a valid Python identifier.

    Args:
        param: The parameter name to validate.
        segment: The original segment string (for error messages).

    Raises:
        RouteValidationError: If the parameter name is invalid.
    """
    if not _VALID_IDENTIFIER.match(param):
        raise RouteValidationError(
            f"Invalid parameter name '{param}' in segment '{segment}'.\n"
            "Parameter names must be valid Python identifiers."
        )


def _validate_file_path(file_path: Path, *, base_path: Path | None = None) -> Path:
    """Validate a route file path for security and correctness.

    Args:
        file_path: Path to the route file.
        base_path: Optional base directory to restrict imports to.

    Returns:
        Resolved absolute path to the route file.

    Raises:
        RouteValidationError: If the path is invalid or insecure.
    """
    resolved_path = file_path.resolve()

    # Check for path traversal attempts (.. as path component, not inside filenames)
    if ".." in file_path.parts:
        raise RouteValidationError(f"Path traversal detected in file path: {file_path}")

    # Validate against allowed base path if set
    if base_path is not None:
        resolved_base = base_path.resolve()
        try:
            resolved_path.relative_to(resolved_base)
        except ValueError:
            raise RouteValidationError(
                f"Route file outside allowed directory: {resolved_path}\n"
                f"Allowed base: {resolved_base}"
            ) from None

    # Ensure it's a route.py file
    if resolved_path.name != "route.py":
        raise RouteValidationError(f"Invalid route file name: {resolved_path.name}")

    return resolved_path


def _path_to_module_name(file_path: Path) -> str:
    """Convert a file path to a deterministic module name.

    Args:
        file_path: Path to the route file.

    Returns:
        Dot-separated module name suitable for sys.modules.

    Raises:
        RouteValidationError: If parameter names in path are invalid.
    """
    # Get path relative to current working directory
    try:
        rel_path = file_path.relative_to(Path.cwd())
    except ValueError:
        rel_path = file_path

    # Convert to parts, excluding the file extension
    parts = list(rel_path.with_suffix("").parts)

    # Convert each part to valid identifier
    converted = []
    for part in parts:
        # Skip group folders (parentheses)
        if part.startswith("(") and part.endswith(")"):
            continue

        # Handle dynamic segments
        if part.startswith("[...") and part.endswith("]"):
            # Catch-all: [...param] -> ___param___
            param = part[4:-1]
            _validate_parameter_name(param, part)
            converted.append(f"___{param}___")
        elif part.startswith("[[") and part.endswith("]]"):
            # Optional: [[param]] -> __param__
            param = part[2:-2]
            _validate_parameter_name(param, part)
            converted.append(f"__{param}__")
        elif part.startswith("[") and part.endswith("]"):
            # Dynamic: [param] -> _param_
            param = part[1:-1]
            _validate_parameter_name(param, part)
            converted.append(f"_{param}_")
        else:
            # Replace any remaining invalid chars with underscore
            safe = part.replace("-", "_").replace(".", "_")
            converted.append(safe)

    return ".".join(converted)


def _register_parent_packages(module_name: str) -> None:
    """Register parent packages in sys.modules for nested module names.

    Args:
        module_name: Dot-separated module name.
    """
    parts = module_name.split(".")
    for i in range(1, len(parts)):
        parent_name = ".".join(parts[:i])
        if parent_name not in sys.modules:
            # Create a placeholder namespace package
            parent_module = ModuleType(parent_name)
            parent_module.__path__ = []
            parent_module.__package__ = parent_name
            sys.modules[parent_name] = parent_module


def _import_module_from_file(
    file_path: Path,
    module_name: str,
) -> ModuleType:
    """Low-level module import from file path.

    Handles spec creation, sys.modules registration, and error cleanup.
    Does NOT handle caching, validation, or parent package registration.

    Args:
        file_path: Path to the Python file to import.
        module_name: Module name for sys.modules registration.

    Returns:
        The imported module.

    Raises:
        RouteValidationError: If spec creation fails or module execution fails.
    """
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise RouteValidationError(f"Cannot create module spec for: {file_path}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module

    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        del sys.modules[module_name]
        raise RouteValidationError(
            f"Failed to import module: {file_path}\nError: {type(exc).__name__}: {exc}"
        ) from exc

    return module


def import_route_module(file_path: Path, *, base_path: Path | None = None) -> ModuleType:
    """Import a route.py file as a Python module.

    Args:
        file_path: Path to the route.py file.
        base_path: Optional base directory to restrict imports to.

    Returns:
        The imported module.

    Raises:
        RouteValidationError: If the path is invalid, file doesn't exist,
            or import fails.
    """
    # Validate path before any file operations
    validated_path = _validate_file_path(file_path, base_path=base_path)

    if not validated_path.exists():
        raise RouteValidationError(f"Route file does not exist: {validated_path}")

    # Detect symlink aliasing via file identity (st_dev, st_ino)
    stat = validated_path.stat()
    file_id = (stat.st_dev, stat.st_ino)
    if file_id in _file_identity_cache:
        cached_name = _file_identity_cache[file_id]
        if cached_name in sys.modules:
            return sys.modules[cached_name]

    # Create a deterministic module name based on file path
    module_name = _path_to_module_name(validated_path)

    # Return cached module if already imported
    if module_name in sys.modules:
        return sys.modules[module_name]

    # Register parent packages for patch() compatibility
    _register_parent_packages(module_name)

    module = _import_module_from_file(validated_path, module_name)

    # Register file identity for symlink detection
    _file_identity_cache[file_id] = module_name

    # Set the module as an attribute of its parent package
    parts = module_name.split(".")
    if len(parts) > 1:
        parent_name = ".".join(parts[:-1])
        if parent_name in sys.modules:
            setattr(sys.modules[parent_name], parts[-1], module)

    return module


def extract_handlers(module: ModuleType, file_path: Path) -> ExtractedRoute:  # noqa: C901
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
    handlers: dict[str, Callable[..., Any]] = {}
    invalid_exports: list[str] = []

    # Extract metadata
    tags = getattr(module, "TAGS", None)
    summary = getattr(module, "SUMMARY", None)
    deprecated = getattr(module, "DEPRECATED", False)

    metadata = RouteMetadata(
        tags=list(tags) if tags else None,
        summary=summary,
        deprecated=bool(deprecated),
    )

    # Extract file-level middleware
    mw_attr = getattr(module, "middleware", None)
    file_middleware = normalize_middleware(
        mw_attr,
        source=f"file {file_path}",
    )

    # Validate file-level middleware entries are async callables
    for i, mw in enumerate(file_middleware):
        if not callable(mw):
            raise RouteValidationError(f"Non-callable middleware at index {i} in {file_path}")
        if not asyncio.iscoroutinefunction(mw):
            raise RouteValidationError(
                f"File-level middleware at index {i} in {file_path} must be async"
            )

    # Collect names that should be skipped during handler validation
    # (functions that are part of the middleware list)
    middleware_names = set()
    if isinstance(file_middleware, (list, tuple)):
        for mw in file_middleware:
            if hasattr(mw, "__name__"):
                middleware_names.add(mw.__name__)

    for name in dir(module):
        # Skip dunder attributes
        if name.startswith("__"):
            continue

        # Skip underscore-prefixed private helpers
        if name.startswith("_"):
            continue

        # Skip uppercase constants (TAGS, SUMMARY, etc.)
        if name.isupper():
            continue

        # Skip the "middleware" attribute itself (list or callable)
        if name == "middleware":
            continue

        obj = getattr(module, name)

        # Check for RouteConfig objects BEFORE generic callable check
        # RouteConfig is callable, so this must come first
        if isinstance(obj, RouteConfig):
            if name.lower() in ALLOWED_HANDLERS:
                handlers[name.lower()] = obj
            else:
                invalid_exports.append(name)
            continue

        # Skip non-callables (imports, etc.)
        if not callable(obj):
            continue

        # Skip imported classes/functions (check module origin)
        if hasattr(obj, "__module__") and obj.__module__ != module.__name__:
            continue

        # Skip middleware functions (they're in the middleware list)
        if name in middleware_names:
            continue

        # Check if it's a valid HTTP verb or websocket
        if name.lower() in ALLOWED_HANDLERS:
            handler_name = name.lower()

            # WebSocket handlers must be async
            if handler_name == "websocket" and not inspect.iscoroutinefunction(obj):
                raise RouteValidationError(
                    f"WebSocket handler must be async in route.py\n"
                    f"  File: {file_path}\n"
                    f"  Hint: Change 'def websocket(...)' to 'async def websocket(...)'"
                )

            handlers[handler_name] = obj
        else:
            invalid_exports.append(name)

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
    """Import a route.py file and extract its handlers (convenience function).

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
    return extract_handlers(module, file_path)
