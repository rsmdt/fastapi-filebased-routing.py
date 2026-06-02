"""Low-level dynamic-import machinery for file-based routing.

Owns path->module-name conversion, parameter-name validation in path encoding,
parent-package registration, spec/exec with ``sys.modules`` cleanup, the
symlink-identity cache, and route-file path validation.

``load_module_from_file`` is the clean public seam used by both
``core/handlers.py`` (via the route-aware ``import_route_module``) and
``core/middleware_loader.py``; nothing here knows about handlers, verbs,
RouteConfig, or middleware.
"""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

from fastapi_filebased_routing.exceptions import RouteValidationError

# Valid Python identifier pattern (alphanumeric + underscore, not starting with digit)
_VALID_IDENTIFIER = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")

# File identity cache: maps (st_dev, st_ino) to module_name for symlink detection.
# This is the SOLE global instance for symlink-identity tracking.
_file_identity_cache: dict[tuple[int, int], str] = {}


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


def validate_route_file_path(file_path: Path, *, base_path: Path | None = None) -> Path:
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


def load_module_from_file(
    file_path: Path,
    module_name: str,
) -> ModuleType:
    """Import a Python file as a module (public seam, low-level).

    The single public entry point for dynamic module loading: creates the spec,
    registers the module in ``sys.modules``, executes it, and cleans up on
    failure. It does NOT validate the path or generate a name — callers supply
    ``module_name``. Used by ``core/handlers.py`` (via the route-aware
    ``import_route_module``) and ``core/middleware_loader.py``.

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

    Validates the path, applies the symlink-identity cache, generates a
    deterministic module name, registers parent packages, and loads the module
    via :func:`load_module_from_file`.

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
    validated_path = validate_route_file_path(file_path, base_path=base_path)

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

    module = load_module_from_file(validated_path, module_name)

    # Register file identity for symlink detection
    _file_identity_cache[file_id] = module_name

    # Set the module as an attribute of its parent package
    parts = module_name.split(".")
    if len(parts) > 1:
        parent_name = ".".join(parts[:-1])
        if parent_name in sys.modules:
            setattr(sys.modules[parent_name], parts[-1], module)

    return module
