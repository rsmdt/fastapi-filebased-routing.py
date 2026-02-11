"""Route filtering for include/exclude deployment topologies.

Filters routes and middleware files based on glob or segment-level
patterns, ensuring excluded code is never imported.
"""

import fnmatch
from collections.abc import Sequence
from pathlib import Path, PurePosixPath

from fastapi_filebased_routing.core.scanner import MiddlewareFile, RouteDefinition
from fastapi_filebased_routing.exceptions import RouteFilterError

_GLOB_CHARS = frozenset("*?[")


def validate_filter_params(
    include: Sequence[str] | None,
    exclude: Sequence[str] | None,
) -> None:
    """Validate that include and exclude are not both non-empty.

    Args:
        include: Allowlist patterns (or None / empty).
        exclude: Denylist patterns (or None / empty).

    Raises:
        RouteFilterError: If both include and exclude are non-empty.
    """
    if include and exclude:
        raise RouteFilterError(
            f"Cannot specify both include and exclude filters: "
            f"include={list(include)}, exclude={list(exclude)}"
        )


def filter_routes(
    routes: list[RouteDefinition],
    *,
    base_path: Path,
    include: Sequence[str] | None,
    exclude: Sequence[str] | None,
) -> list[RouteDefinition]:
    """Filter route definitions by include/exclude patterns.

    Patterns match against the relative directory path (posix-normalized)
    from base_path to each route.py's parent.

    Args:
        routes: List of discovered route definitions.
        base_path: Root directory of the route tree.
        include: Allowlist patterns. Only matching routes are kept.
        exclude: Denylist patterns. Matching routes are removed.

    Returns:
        Filtered list of route definitions.

    Raises:
        RouteFilterError: If both include and exclude are non-empty.
    """
    validate_filter_params(include, exclude)

    if not include and not exclude:
        return routes

    result: list[RouteDefinition] = []
    for route in routes:
        rel = _relative_directory(route.file_path, base_path)

        if (include and _matches_any_pattern(rel, include)) or (
            exclude and not _matches_any_pattern(rel, exclude)
        ):
            result.append(route)

    return result


def compute_active_directories(
    routes: list[RouteDefinition],
    base_path: Path,
) -> set[Path]:
    """Compute the set of directories that are ancestors of surviving routes.

    This ensures parent middleware files (e.g., root _middleware.py) still
    apply to included child routes.

    Args:
        routes: Filtered list of route definitions.
        base_path: Root directory of the route tree.

    Returns:
        Set of directory paths from base_path to each route's parent.
    """
    active: set[Path] = set()

    for route in routes:
        route_dir = route.file_path.parent
        # Walk from base_path to route_dir
        active.add(base_path)
        try:
            rel = route_dir.relative_to(base_path)
        except ValueError:
            continue

        current = base_path
        for part in rel.parts:
            current = current / part
            active.add(current)

    return active


def filter_middleware_files(
    middleware_files: list[MiddlewareFile],
    active_directories: set[Path],
) -> list[MiddlewareFile]:
    """Filter middleware files to only those in active directories.

    Args:
        middleware_files: All discovered middleware files.
        active_directories: Set of directories that are ancestors
            of surviving routes.

    Returns:
        Filtered list of middleware files.
    """
    return [mw for mw in middleware_files if mw.directory in active_directories]


def _relative_directory(file_path: Path, base_path: Path) -> str:
    """Compute the posix-normalized relative directory path.

    Args:
        file_path: Absolute path to a route.py file.
        base_path: Root directory of the route tree.

    Returns:
        Posix-normalized relative path string, or '.' for root.
    """
    rel = file_path.parent.relative_to(base_path)
    posix = PurePosixPath(rel).as_posix()
    return posix if posix != "." else "."


def _has_glob_characters(pattern: str) -> bool:
    """Check if a pattern contains glob metacharacters."""
    return bool(_GLOB_CHARS & set(pattern))


def _matches_any_pattern(relative_path: str, patterns: Sequence[str]) -> bool:
    """Check if a relative path matches any of the given patterns.

    Two matching modes:
    1. Glob patterns (containing *, ?, [): matched via fnmatch against
       the full relative path.
    2. Bare names (no wildcards): segment-level matching — checked
       against each directory segment in the path.

    Args:
        relative_path: Posix-normalized relative directory path.
        patterns: Sequence of pattern strings.

    Returns:
        True if any pattern matches, False otherwise.
    """
    for pattern in patterns:
        if _has_glob_characters(pattern):
            if fnmatch.fnmatch(relative_path, pattern):
                return True
        else:
            # Segment-level matching
            parts = relative_path.split("/") if relative_path != "." else []
            if pattern in parts:
                return True
    return False
