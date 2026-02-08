"""Path segment parser for file-based routing.

Converts directory names into FastAPI path patterns:
- [param] -> {param} (required parameter)
- (group) -> skipped (route group, not in URL)
- [...param] -> {param:path} (catch-all parameter)
- [[param]] -> {param} with optional flag (optional parameter)
"""

import re
from dataclasses import dataclass
from enum import Enum

from fastapi_filebased_routing.exceptions import PathParseError


class SegmentType(Enum):
    """Type of a URL path segment."""

    STATIC = "static"
    DYNAMIC = "dynamic"
    CATCH_ALL = "catch_all"
    OPTIONAL = "optional"
    GROUP = "group"


@dataclass(frozen=True)
class PathSegment:
    """A parsed URL path segment with type and name."""

    name: str
    segment_type: SegmentType
    original: str

    @property
    def is_parameter(self) -> bool:
        """Check if this segment represents a path parameter."""
        return self.segment_type in (
            SegmentType.DYNAMIC,
            SegmentType.CATCH_ALL,
            SegmentType.OPTIONAL,
        )

    def to_fastapi_segment(self) -> str | None:
        """Convert this segment to FastAPI path syntax.

        Returns:
            FastAPI path segment string, or None for GROUP segments.

        Examples:
            STATIC "users" -> "users"
            DYNAMIC "id" -> "{id}"
            CATCH_ALL "path" -> "{path:path}"
            OPTIONAL "version" -> "{version}"
            GROUP "admin" -> None
        """
        match self.segment_type:
            case SegmentType.STATIC:
                return self.name
            case SegmentType.DYNAMIC:
                return f"{{{self.name}}}"
            case SegmentType.CATCH_ALL:
                return f"{{{self.name}:path}}"
            case SegmentType.OPTIONAL:
                return f"{{{self.name}}}"
            case SegmentType.GROUP:
                return None


_OPTIONAL_PATTERN = re.compile(r"^\[\[([a-z_][a-z0-9_]*)\]\]$")
_CATCH_ALL_PATTERN = re.compile(r"^\[\.\.\.([a-z_][a-z0-9_]*)\]$")
_DYNAMIC_PATTERN = re.compile(r"^\[([a-z_][a-z0-9_]*)\]$")
_GROUP_PATTERN = re.compile(r"^\(([a-zA-Z_][a-zA-Z0-9_]*)\)$")
_STATIC_PATTERN = re.compile(r"^[a-z][a-z0-9_-]*$")


def parse_path_segment(segment: str) -> PathSegment:
    """Parse a single directory name into a PathSegment.

    Args:
        segment: Directory name to parse.

    Returns:
        PathSegment with detected type and extracted name.

    Raises:
        PathParseError: If segment has invalid syntax.

    Examples:
        "users" -> PathSegment(name="users", segment_type=STATIC, ...)
        "[id]" -> PathSegment(name="id", segment_type=DYNAMIC, ...)
        "[[version]]" -> PathSegment(name="version", segment_type=OPTIONAL, ...)
        "[...path]" -> PathSegment(name="path", segment_type=CATCH_ALL, ...)
        "(admin)" -> PathSegment(name="admin", segment_type=GROUP, ...)
    """
    if not segment:
        raise PathParseError("Empty segment")

    if match := _OPTIONAL_PATTERN.match(segment):
        return PathSegment(
            name=match.group(1),
            segment_type=SegmentType.OPTIONAL,
            original=segment,
        )

    if match := _CATCH_ALL_PATTERN.match(segment):
        return PathSegment(
            name=match.group(1),
            segment_type=SegmentType.CATCH_ALL,
            original=segment,
        )

    if match := _DYNAMIC_PATTERN.match(segment):
        return PathSegment(
            name=match.group(1),
            segment_type=SegmentType.DYNAMIC,
            original=segment,
        )

    if match := _GROUP_PATTERN.match(segment):
        return PathSegment(
            name=match.group(1),
            segment_type=SegmentType.GROUP,
            original=segment,
        )

    if _STATIC_PATTERN.match(segment):
        return PathSegment(
            name=segment,
            segment_type=SegmentType.STATIC,
            original=segment,
        )

    raise PathParseError(
        f"Invalid path segment '{segment}'. "
        f"Use [param], [[param]], [...param], (group), or lowercase-with-dashes."
    )


def parse_path(path_parts: list[str]) -> list[PathSegment]:
    """Parse a list of directory names into PathSegments.

    Args:
        path_parts: List of directory names from a file path.

    Returns:
        List of parsed PathSegment objects.

    Raises:
        PathParseError: If any segment has invalid syntax or if a catch-all
            segment is not the last segment.

    Examples:
        ["api", "users"] -> [PathSegment(STATIC, "api"), PathSegment(STATIC, "users")]
        ["users", "[id]"] -> [PathSegment(STATIC, "users"), PathSegment(DYNAMIC, "id")]
    """
    segments = []
    catch_all_seen = False

    for part in path_parts:
        if catch_all_seen:
            raise PathParseError(
                f"Catch-all parameter must be the last path segment. "
                f"Found '{part}' after catch-all."
            )

        segment = parse_path_segment(part)
        segments.append(segment)

        if segment.segment_type == SegmentType.CATCH_ALL:
            catch_all_seen = True

    return segments


def segments_to_fastapi_path(segments: list[PathSegment]) -> str:
    """Convert PathSegments to a FastAPI path string.

    Args:
        segments: List of PathSegment objects.

    Returns:
        FastAPI-compatible path string with leading slash.

    Examples:
        [STATIC("users")] -> "/users"
        [STATIC("users"), DYNAMIC("id")] -> "/users/{id}"
        [GROUP("admin"), STATIC("settings")] -> "/settings"
        [] -> "/"
    """
    parts = []
    for segment in segments:
        fastapi_part = segment.to_fastapi_segment()
        if fastapi_part is not None:
            parts.append(fastapi_part)

    return "/" + "/".join(parts) if parts else "/"
