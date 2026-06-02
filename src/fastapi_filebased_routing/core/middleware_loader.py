"""Loading and collection of directory _middleware.py files.

Framework-agnostic loading/validation of directory ``_middleware.py`` files into
a ``{directory: middleware tuple}`` map, plus collecting the parent-before-child
cascade applicable to a given route directory.

Uses ``module_loader.load_module_from_file`` (the public seam) and the shared
``routes`` vocabulary. No FastAPI dependency — it operates purely on discovery
output, so it belongs in the framework-agnostic core layer.
"""

from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

from fastapi_filebased_routing.core.discovery import DirectoryMiddleware
from fastapi_filebased_routing.core.module_loader import load_module_from_file
from fastapi_filebased_routing.core.routes import normalize_middleware, validate_middleware_entries
from fastapi_filebased_routing.exceptions import MiddlewareValidationError


def _import_middleware_module(file_path: Path, base_path: Path) -> ModuleType:
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
        return load_module_from_file(file_path, module_name)
    except Exception as exc:
        raise MiddlewareValidationError(f"Failed to import {file_path}: {exc}") from exc


def load_directory_middleware(
    directory_middleware: list[DirectoryMiddleware],
    base_path: Path,
) -> dict[Path, tuple[Callable[..., Any], ...]]:
    """Import _middleware.py files and extract their middleware callables.

    Returns a dict mapping directory path to its middleware tuple.
    Validates all middleware are async callables.

    Args:
        directory_middleware: List of DirectoryMiddleware objects to import.
        base_path: Base directory for module import.

    Returns:
        Dictionary mapping directory Path to tuple of middleware callables.

    Raises:
        MiddlewareValidationError: If import fails, middleware is invalid,
            or middleware is not async.
    """
    result: dict[Path, tuple[Callable[..., Any], ...]] = {}

    for mw_file in directory_middleware:
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
        validate_middleware_entries(
            middleware_list,
            source=str(mw_file.file_path),
            error_class=MiddlewareValidationError,
        )

        result[mw_file.directory] = tuple(middleware_list)

    return result


def collect_directory_middleware(
    route_dir: Path,
    base_path: Path,
    dir_middleware: dict[Path, tuple[Callable[..., Any], ...]],
) -> tuple[Callable[..., Any], ...]:
    """Collect directory middleware applicable to a route directory.

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
