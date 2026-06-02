"""Pipeline stage 2: filesystem discovery for file-based routing.

Walks the directory tree to find ``route.py`` and ``_middleware.py`` files,
applies security filtering (dotfiles, ``__pycache__``, symlink-escape), parses
route directories into RouteDefinitions (including 2^n optional-variant
expansion), and records directory-middleware locations sorted by depth.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from fastapi_filebased_routing.core.paths import (
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
class DirectoryMiddleware:
    """A discovered _middleware.py file with its directory depth.

    Directory middleware cascades to subdirectories (parent before child).

    Attributes:
        file_path: Absolute path to the _middleware.py file.
        directory: Absolute path to the directory containing the file.
        depth: Directory depth relative to base path (0 = base).
    """

    file_path: Path
    directory: Path
    depth: int


def _scan_directory(base_path: Path | str, glob_pattern: str) -> Iterator[tuple[Path, Path]]:
    """Walk a directory tree and yield valid files matching a glob pattern.

    Resolves the base path, validates it exists and is a directory, then
    yields files that pass security checks (__pycache__, hidden dirs, symlinks).

    Args:
        base_path: Root directory to scan.
        glob_pattern: Glob pattern to match (e.g., "route.py", "_middleware.py").

    Yields:
        Tuples of (file_path, resolved_base) for each valid file found.

    Raises:
        RouteDiscoveryError: If base_path doesn't exist or isn't a directory.
    """
    base = Path(base_path).resolve()

    if not base.exists():
        raise RouteDiscoveryError(f"Base path does not exist: {base}")
    if not base.is_dir():
        raise RouteDiscoveryError(f"Base path is not a directory: {base}")

    for found_file in base.rglob(glob_pattern):
        if "__pycache__" in found_file.parts:
            continue
        # Filter dotfile components only under base — anything in the
        # ancestors of base is incidental layout (e.g. a worktree at
        # .worktree/main, a project under .venvs/) and shouldn't reject
        # the user's own routes.
        if any(part.startswith(".") for part in found_file.relative_to(base).parts):
            continue
        resolved_file = found_file.resolve()
        if not _is_path_within(resolved_file, base):
            continue
        yield found_file, base


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
    routes: list[RouteDefinition] = []

    for route_file, base in _scan_directory(base_path, "route.py"):
        relative_dir = route_file.parent.relative_to(base)
        segments = parse_path(list(relative_dir.parts))
        routes.extend(_generate_route_variants(segments, route_file))

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


def scan_directory_middleware(base_path: Path | str) -> list[DirectoryMiddleware]:
    """Scan a directory tree for _middleware.py files.

    Walks the directory tree recursively, finds all _middleware.py files,
    and records their depth for ordering (parent before child).

    Args:
        base_path: Root directory to scan for _middleware.py files.

    Returns:
        List of DirectoryMiddleware objects, sorted by depth (shallowest first).
        Empty list if no _middleware.py files are found.

    Raises:
        RouteDiscoveryError: If base_path doesn't exist or isn't a directory.

    Examples:
        files = scan_directory_middleware("app")
        for mw_file in files:
            print(f"{mw_file.depth}: {mw_file.file_path}")
    """
    directory_middleware: list[DirectoryMiddleware] = []

    for mw_file, base in _scan_directory(base_path, "_middleware.py"):
        directory = mw_file.parent
        try:
            relative_dir = directory.relative_to(base)
            depth = len(relative_dir.parts)
        except ValueError:
            continue

        directory_middleware.append(
            DirectoryMiddleware(
                file_path=mw_file,
                directory=directory,
                depth=depth,
            )
        )

    return sorted(directory_middleware, key=lambda mf: mf.depth)
