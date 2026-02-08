"""Tests for the core parser module."""

import pytest

from fastapi_filebased_routing.core.parser import (
    PathSegment,
    SegmentType,
    parse_path,
    parse_path_segment,
    segments_to_fastapi_path,
)
from fastapi_filebased_routing.exceptions import PathParseError


class TestSegmentType:
    def test_segment_types_exist(self):
        assert SegmentType.STATIC
        assert SegmentType.DYNAMIC
        assert SegmentType.CATCH_ALL
        assert SegmentType.OPTIONAL
        assert SegmentType.GROUP


class TestPathSegment:
    def test_frozen_dataclass(self):
        segment = PathSegment("users", SegmentType.STATIC, "users")
        with pytest.raises(AttributeError):
            segment.name = "changed"

    def test_is_parameter_for_dynamic(self):
        segment = PathSegment("id", SegmentType.DYNAMIC, "[id]")
        assert segment.is_parameter is True

    def test_is_parameter_for_optional(self):
        segment = PathSegment("version", SegmentType.OPTIONAL, "[[version]]")
        assert segment.is_parameter is True

    def test_is_parameter_for_catch_all(self):
        segment = PathSegment("path", SegmentType.CATCH_ALL, "[...path]")
        assert segment.is_parameter is True

    def test_is_parameter_for_static(self):
        segment = PathSegment("users", SegmentType.STATIC, "users")
        assert segment.is_parameter is False

    def test_is_parameter_for_group(self):
        segment = PathSegment("admin", SegmentType.GROUP, "(admin)")
        assert segment.is_parameter is False

    def test_to_fastapi_segment_static(self):
        segment = PathSegment("users", SegmentType.STATIC, "users")
        assert segment.to_fastapi_segment() == "users"

    def test_to_fastapi_segment_dynamic(self):
        segment = PathSegment("id", SegmentType.DYNAMIC, "[id]")
        assert segment.to_fastapi_segment() == "{id}"

    def test_to_fastapi_segment_optional(self):
        segment = PathSegment("version", SegmentType.OPTIONAL, "[[version]]")
        assert segment.to_fastapi_segment() == "{version}"

    def test_to_fastapi_segment_catch_all(self):
        segment = PathSegment("path", SegmentType.CATCH_ALL, "[...path]")
        assert segment.to_fastapi_segment() == "{path:path}"

    def test_to_fastapi_segment_group(self):
        segment = PathSegment("admin", SegmentType.GROUP, "(admin)")
        assert segment.to_fastapi_segment() is None


class TestParsePathSegment:
    def test_static_segment(self):
        segment = parse_path_segment("users")
        assert segment.name == "users"
        assert segment.segment_type == SegmentType.STATIC
        assert segment.original == "users"
        assert not segment.is_parameter
        assert segment.to_fastapi_segment() == "users"

    def test_static_segment_with_hyphen(self):
        segment = parse_path_segment("my-projects")
        assert segment.name == "my-projects"
        assert segment.segment_type == SegmentType.STATIC
        assert segment.to_fastapi_segment() == "my-projects"

    def test_static_segment_with_underscore(self):
        segment = parse_path_segment("user_data")
        assert segment.name == "user_data"
        assert segment.segment_type == SegmentType.STATIC
        assert segment.to_fastapi_segment() == "user_data"

    def test_dynamic_parameter(self):
        segment = parse_path_segment("[id]")
        assert segment.name == "id"
        assert segment.segment_type == SegmentType.DYNAMIC
        assert segment.original == "[id]"
        assert segment.is_parameter
        assert segment.to_fastapi_segment() == "{id}"

    def test_dynamic_parameter_with_underscore(self):
        segment = parse_path_segment("[user_id]")
        assert segment.name == "user_id"
        assert segment.segment_type == SegmentType.DYNAMIC
        assert segment.original == "[user_id]"
        assert segment.is_parameter
        assert segment.to_fastapi_segment() == "{user_id}"

    def test_optional_parameter(self):
        segment = parse_path_segment("[[version]]")
        assert segment.name == "version"
        assert segment.segment_type == SegmentType.OPTIONAL
        assert segment.original == "[[version]]"
        assert segment.is_parameter
        assert segment.to_fastapi_segment() == "{version}"

    def test_catch_all_parameter(self):
        segment = parse_path_segment("[...path]")
        assert segment.name == "path"
        assert segment.segment_type == SegmentType.CATCH_ALL
        assert segment.original == "[...path]"
        assert segment.is_parameter
        assert segment.to_fastapi_segment() == "{path:path}"

    def test_route_group(self):
        segment = parse_path_segment("(admin)")
        assert segment.name == "admin"
        assert segment.segment_type == SegmentType.GROUP
        assert segment.original == "(admin)"
        assert not segment.is_parameter
        assert segment.to_fastapi_segment() is None

    def test_route_group_with_underscore(self):
        segment = parse_path_segment("(admin_panel)")
        assert segment.name == "admin_panel"
        assert segment.segment_type == SegmentType.GROUP

    def test_empty_segment_raises_error(self):
        with pytest.raises(PathParseError, match="Empty segment"):
            parse_path_segment("")

    def test_unclosed_bracket_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("[")

    def test_unclosed_dynamic_parameter_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("[id")

    def test_empty_bracket_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("[]")

    def test_empty_optional_bracket_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("[[]]")

    def test_empty_catch_all_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("[...]")

    def test_invalid_identifier_numeric_start_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("[123]")

    def test_invalid_identifier_hyphen_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("[my-param]")

    def test_invalid_capitalized_static_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("InvalidCapitalized")

    def test_invalid_static_starting_with_number_raises_error(self):
        with pytest.raises(PathParseError, match="Invalid path segment"):
            parse_path_segment("1users")


class TestParsePath:
    def test_simple_static_path(self):
        segments = parse_path(["users"])
        assert len(segments) == 1
        assert segments[0].name == "users"
        assert segments[0].segment_type == SegmentType.STATIC

    def test_nested_static_path(self):
        segments = parse_path(["api", "v1", "users"])
        assert len(segments) == 3
        assert all(s.segment_type == SegmentType.STATIC for s in segments)
        assert [s.name for s in segments] == ["api", "v1", "users"]

    def test_path_with_dynamic_parameter(self):
        segments = parse_path(["api", "users", "[user_id]"])
        assert len(segments) == 3
        assert segments[0].segment_type == SegmentType.STATIC
        assert segments[1].segment_type == SegmentType.STATIC
        assert segments[2].segment_type == SegmentType.DYNAMIC
        assert segments[2].name == "user_id"

    def test_path_with_optional_parameter(self):
        segments = parse_path(["api", "[[version]]", "users"])
        assert len(segments) == 3
        assert segments[0].segment_type == SegmentType.STATIC
        assert segments[1].segment_type == SegmentType.OPTIONAL
        assert segments[2].segment_type == SegmentType.STATIC

    def test_path_with_route_group(self):
        segments = parse_path(["(admin)", "settings"])
        assert len(segments) == 2
        assert segments[0].segment_type == SegmentType.GROUP
        assert segments[0].name == "admin"
        assert segments[1].segment_type == SegmentType.STATIC

    def test_path_with_catch_all_at_end(self):
        segments = parse_path(["files", "[...path]"])
        assert len(segments) == 2
        assert segments[0].segment_type == SegmentType.STATIC
        assert segments[1].segment_type == SegmentType.CATCH_ALL
        assert segments[1].name == "path"

    def test_catch_all_must_be_last(self):
        with pytest.raises(
            PathParseError, match="Catch-all parameter must be the last path segment"
        ):
            parse_path(["api", "[...path]", "users"])

    def test_catch_all_followed_by_static_raises_error(self):
        with pytest.raises(
            PathParseError, match="Catch-all parameter must be the last path segment"
        ):
            parse_path(["[...files]", "metadata"])

    def test_catch_all_followed_by_dynamic_raises_error(self):
        with pytest.raises(
            PathParseError, match="Catch-all parameter must be the last path segment"
        ):
            parse_path(["[...files]", "[id]"])

    def test_empty_path_list(self):
        segments = parse_path([])
        assert segments == []

    def test_complex_mixed_path(self):
        segments = parse_path(["(admin)", "api", "[[version]]", "users", "[user_id]"])
        assert len(segments) == 5
        assert segments[0].segment_type == SegmentType.GROUP
        assert segments[1].segment_type == SegmentType.STATIC
        assert segments[2].segment_type == SegmentType.OPTIONAL
        assert segments[3].segment_type == SegmentType.STATIC
        assert segments[4].segment_type == SegmentType.DYNAMIC


class TestSegmentsToFastapiPath:
    def test_static_only(self):
        segments = [
            PathSegment("api", SegmentType.STATIC, "api"),
            PathSegment("v1", SegmentType.STATIC, "v1"),
            PathSegment("users", SegmentType.STATIC, "users"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/api/v1/users"

    def test_single_static_segment(self):
        segments = [PathSegment("users", SegmentType.STATIC, "users")]
        path = segments_to_fastapi_path(segments)
        assert path == "/users"

    def test_with_dynamic_parameter(self):
        segments = [
            PathSegment("api", SegmentType.STATIC, "api"),
            PathSegment("users", SegmentType.STATIC, "users"),
            PathSegment("user_id", SegmentType.DYNAMIC, "[user_id]"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/api/users/{user_id}"

    def test_with_optional_parameter(self):
        segments = [
            PathSegment("api", SegmentType.STATIC, "api"),
            PathSegment("version", SegmentType.OPTIONAL, "[[version]]"),
            PathSegment("users", SegmentType.STATIC, "users"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/api/{version}/users"

    def test_with_catch_all(self):
        segments = [
            PathSegment("files", SegmentType.STATIC, "files"),
            PathSegment("path", SegmentType.CATCH_ALL, "[...path]"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/files/{path:path}"

    def test_with_route_group_excluded(self):
        segments = [
            PathSegment("admin", SegmentType.GROUP, "(admin)"),
            PathSegment("settings", SegmentType.STATIC, "settings"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/settings"

    def test_multiple_groups_excluded(self):
        segments = [
            PathSegment("admin", SegmentType.GROUP, "(admin)"),
            PathSegment("protected", SegmentType.GROUP, "(protected)"),
            PathSegment("users", SegmentType.STATIC, "users"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/users"

    def test_empty_segments_returns_root(self):
        path = segments_to_fastapi_path([])
        assert path == "/"

    def test_only_groups_returns_root(self):
        segments = [
            PathSegment("admin", SegmentType.GROUP, "(admin)"),
            PathSegment("protected", SegmentType.GROUP, "(protected)"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/"

    def test_complex_mixed_path(self):
        segments = [
            PathSegment("admin", SegmentType.GROUP, "(admin)"),
            PathSegment("api", SegmentType.STATIC, "api"),
            PathSegment("version", SegmentType.OPTIONAL, "[[version]]"),
            PathSegment("users", SegmentType.STATIC, "users"),
            PathSegment("user_id", SegmentType.DYNAMIC, "[user_id]"),
        ]
        path = segments_to_fastapi_path(segments)
        assert path == "/api/{version}/users/{user_id}"
