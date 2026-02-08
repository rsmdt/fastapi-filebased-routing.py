"""Directory scanner for file-based routing.

Walks the directory tree to discover route.py files and extract
route definitions with their paths.
"""

from dataclasses import dataclass
from pathlib import Path

from fastapi_filebased_routing.core.parser import (
    PathSegment,
    SegmentType,
    parse_path,
    segments_to_fastapi_path,
)
from fastapi_filebased_routing.exceptions import RouteDiscoveryError


@dataclass(frozen=True)
class RouteDefinition:
    """A discovered route with its filesystem path and parsed segments.

    Attributes:
        path: FastAPI-style path string (e.g., /users/{id})
        file_path: Absolute path to the route.py file
        segments: Tuple of parsed PathSegment objects
    """

    path: str
    file_path: Path
    segments: tuple[PathSegment, ...]

    @property
    def has_optional_params(self) -> bool:
        """Check if this route has any optional parameters.

        Returns:
            True if any segment is OPTIONAL type, False otherwise.
        """
        return any(s.segment_type == SegmentType.OPTIONAL for s in self.segments)

    @property
    def parameters(self) -> list[PathSegment]:
        """Get all parameter segments (dynamic, catch-all, or optional).

        Returns:
            List of PathSegment objects that represent parameters.
        """
        return [s for s in self.segments if s.is_parameter]


@dataclass(frozen=True)
class MiddlewareFile:
    """A discovered _middleware.py file with its directory depth.

    Attributes:
        file_path: Absolute path to the _middleware.py file.
        directory: Absolute path to the directory containing the file.
        depth: Directory depth relative to base path (0 = base).
    """

    file_path: Path
    directory: Path
    depth: int


def scan_routes(base_path: Path | str) -> list[RouteDefinition]:
    """Scan a directory tree for route.py files and generate route definitions.

    Walks the directory tree recursively, finds all route.py files,
    parses their directory paths into segments, and generates route
    variants for optional parameters.

    Args:
        base_path: Root directory to scan for route.py files.

    Returns:
        List of RouteDefinition objects, one for each discovered route.
        Routes with optional parameters generate multiple variants (2^n).

    Raises:
        RouteDiscoveryError: If base_path doesn't exist or isn't a directory.
        PathParseError: If any directory name has invalid syntax.

    Examples:
        routes = scan_routes("app")
        for route in routes:
            print(f"{route.path} -> {route.file_path}")
    """
    base = Path(base_path).resolve()

    if not base.exists():
        raise RouteDiscoveryError(f"Base path does not exist: {base}")
    if not base.is_dir():
        raise RouteDiscoveryError(f"Base path is not a directory: {base}")

    routes: list[RouteDefinition] = []

    for route_file in base.rglob("route.py"):
        # Skip __pycache__ directories
        if "__pycache__" in route_file.parts:
            continue

        # Skip hidden directories (starting with .)
        if any(part.startswith(".") for part in route_file.parts):
            continue

        # Security: Resolve symlinks and verify file is within base path
        resolved_file = route_file.resolve()
        if not _is_path_within(resolved_file, base):
            continue

        # Get path relative to base
        relative_dir = route_file.parent.relative_to(base)
        path_parts = list(relative_dir.parts)

        # Parse directory names into segments
        segments = parse_path(path_parts)

        # Handle optional parameters by generating route variants
        route_variants = _generate_route_variants(segments, route_file)
        routes.extend(route_variants)

    return routes


def _is_path_within(path: Path, base: Path) -> bool:
    """Check if a resolved path is within a base directory.

    Args:
        path: Resolved path to check.
        base: Base directory path.

    Returns:
        True if path is within base, False otherwise.
    """
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


def _generate_route_variants(
    segments: list[PathSegment],
    file_path: Path,
) -> list[RouteDefinition]:
    """Generate route variants for optional parameters.

    For n optional parameters, generates 2^n route variants by including
    or excluding each optional parameter in all combinations.

    Args:
        segments: List of parsed PathSegment objects.
        file_path: Path to the route.py file.

    Returns:
        List of RouteDefinition objects. If no optional parameters exist,
        returns a single RouteDefinition. Otherwise, returns 2^n variants.

    Algorithm:
        1. Find indices where segment_type == OPTIONAL
        2. If no optional segments: return single RouteDefinition
        3. For each mask in range(2^n):
           a. Build variant_segments by including/excluding optional per mask bit
           b. Convert variant_segments to FastAPI path string
           c. Create RouteDefinition for this variant
        4. Return all variants (2^n RouteDefinitions)

    Examples:
        Single optional: [[version]]/users
            -> 2 variants: /users, /{version}/users

        Two optional: [[a]]/[[b]]/items
            -> 4 variants: /items, /{a}/items, /{b}/items, /{a}/{b}/items
    """
    optional_indices = [i for i, s in enumerate(segments) if s.segment_type == SegmentType.OPTIONAL]

    if not optional_indices:
        # No optional params, single route
        path = segments_to_fastapi_path(segments)
        return [
            RouteDefinition(
                path=path,
                file_path=file_path,
                segments=tuple(segments),
            )
        ]

    # Generate 2^n variants for n optional params
    variants: list[RouteDefinition] = []
    n_optional = len(optional_indices)

    for mask in range(2**n_optional):
        # Build segments for this variant
        variant_segments: list[PathSegment] = []

        for i, segment in enumerate(segments):
            if i in optional_indices:
                # Check if this optional param is included in this variant
                optional_idx = optional_indices.index(i)
                if mask & (1 << optional_idx):
                    variant_segments.append(segment)
            else:
                variant_segments.append(segment)

        path = segments_to_fastapi_path(variant_segments)
        variants.append(
            RouteDefinition(
                path=path,
                file_path=file_path,
                segments=tuple(variant_segments),
            )
        )

    return variants


def scan_middleware(base_path: Path | str) -> list[MiddlewareFile]:
    """Scan a directory tree for _middleware.py files.

    Walks the directory tree recursively, finds all _middleware.py files,
    and records their depth for ordering (parent before child).

    Args:
        base_path: Root directory to scan for _middleware.py files.

    Returns:
        List of MiddlewareFile objects, sorted by depth (shallowest first).
        Empty list if no _middleware.py files are found.

    Raises:
        RouteDiscoveryError: If base_path doesn't exist or isn't a directory.

    Examples:
        files = scan_middleware("app")
        for mw_file in files:
            print(f"{mw_file.depth}: {mw_file.file_path}")
    """
    base = Path(base_path).resolve()

    if not base.exists():
        raise RouteDiscoveryError(f"Base path does not exist: {base}")
    if not base.is_dir():
        raise RouteDiscoveryError(f"Base path is not a directory: {base}")

    middleware_files: list[MiddlewareFile] = []

    for mw_file in base.rglob("_middleware.py"):
        # Skip __pycache__ directories
        if "__pycache__" in mw_file.parts:
            continue

        # Skip hidden directories (starting with .)
        if any(part.startswith(".") for part in mw_file.parts):
            continue

        # Security: Resolve symlinks and verify file is within base path
        resolved_file = mw_file.resolve()
        if not _is_path_within(resolved_file, base):
            continue

        # Get directory containing the middleware file
        directory = mw_file.parent

        # Calculate depth relative to base
        try:
            relative_dir = directory.relative_to(base)
            depth = len(relative_dir.parts)
        except ValueError:
            # Should not happen due to _is_path_within check, but handle defensively
            continue

        middleware_files.append(
            MiddlewareFile(
                file_path=mw_file,
                directory=directory,
                depth=depth,
            )
        )

    # Sort by depth (shallowest first)
    return sorted(middleware_files, key=lambda mf: mf.depth)
