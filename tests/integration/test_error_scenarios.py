"""Integration tests for error scenarios in file-based routing.

These tests exercise the full pipeline through `create_router_from_path`
and verify that all errors are raised at startup (router creation time),
not during request handling. Each exception type is tested at least once,
and error messages are verified to be descriptive and actionable.
"""

from pathlib import Path

import pytest

from fastapi_filebased_routing import create_router_from_path
from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    FileBasedRoutingError,
    PathParseError,
    RouteDiscoveryError,
    RouteValidationError,
)


class TestRouteDiscoveryErrorNonexistentPath:
    """RouteDiscoveryError when base path does not exist."""

    def test_nonexistent_base_path_raises_route_discovery_error(self, tmp_path: Path):
        """Nonexistent directory raises RouteDiscoveryError at startup."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(RouteDiscoveryError, match="does not exist"):
            create_router_from_path(nonexistent)

    def test_nonexistent_path_error_includes_resolved_path(self, tmp_path: Path):
        """Error message includes the resolved absolute path for debugging."""
        nonexistent = tmp_path / "missing_routes"

        with pytest.raises(RouteDiscoveryError) as exc_info:
            create_router_from_path(nonexistent)

        error_message = str(exc_info.value)
        assert "missing_routes" in error_message

    def test_nonexistent_path_is_subclass_of_base_error(self, tmp_path: Path):
        """RouteDiscoveryError is catchable via FileBasedRoutingError base class."""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(FileBasedRoutingError):
            create_router_from_path(nonexistent)

    def test_deeply_nested_nonexistent_path(self, tmp_path: Path):
        """Deeply nested nonexistent path raises RouteDiscoveryError."""
        deep_path = tmp_path / "a" / "b" / "c" / "d" / "nonexistent"

        with pytest.raises(RouteDiscoveryError, match="does not exist"):
            create_router_from_path(deep_path)


class TestRouteDiscoveryErrorFileNotDirectory:
    """RouteDiscoveryError when base path is a file instead of a directory."""

    def test_file_as_base_path_raises_route_discovery_error(self, tmp_path: Path):
        """Passing a file path instead of a directory raises RouteDiscoveryError."""
        file_path = tmp_path / "not_a_dir.txt"
        file_path.write_text("this is a file")

        with pytest.raises(RouteDiscoveryError, match="not a directory"):
            create_router_from_path(file_path)

    def test_file_path_error_includes_path_for_debugging(self, tmp_path: Path):
        """Error message includes the file path so the developer can fix it."""
        config_file = tmp_path / "config.json"
        config_file.write_text("{}")

        with pytest.raises(RouteDiscoveryError) as exc_info:
            create_router_from_path(config_file)

        error_message = str(exc_info.value)
        assert "config.json" in error_message

    def test_route_py_file_itself_as_base_path(self, tmp_path: Path):
        """Passing a route.py file as base path raises RouteDiscoveryError."""
        route_file = tmp_path / "route.py"
        route_file.write_text("def get(): return {}")

        with pytest.raises(RouteDiscoveryError, match="not a directory"):
            create_router_from_path(route_file)


class TestPathParseErrorInvalidSyntax:
    """PathParseError when directory name has invalid syntax."""

    def test_unclosed_bracket_raises_path_parse_error(
        self, tmp_path: Path, create_route_file
    ):
        """Directory with unclosed bracket raises PathParseError during scanning."""
        invalid_dir = tmp_path / "[unclosed"
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(tmp_path)

    def test_uppercase_directory_name_raises_path_parse_error(
        self, tmp_path: Path, create_route_file
    ):
        """Directory with uppercase letters raises PathParseError."""
        invalid_dir = tmp_path / "InvalidName"
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(tmp_path)

    def test_path_parse_error_includes_segment_name(
        self, tmp_path: Path, create_route_file
    ):
        """Error message includes the invalid segment for easy identification."""
        bad_segment = "[bad[segment"
        invalid_dir = tmp_path / bad_segment
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        with pytest.raises(PathParseError) as exc_info:
            create_router_from_path(tmp_path)

        assert bad_segment in str(exc_info.value)

    def test_path_parse_error_includes_usage_hint(
        self, tmp_path: Path, create_route_file
    ):
        """Error message includes a hint about valid segment formats."""
        invalid_dir = tmp_path / "BAD_DIR"
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        with pytest.raises(PathParseError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "[param]" in error_message or "lowercase" in error_message

    def test_path_parse_error_is_subclass_of_base_error(
        self, tmp_path: Path, create_route_file
    ):
        """PathParseError is catchable via FileBasedRoutingError base class."""
        invalid_dir = tmp_path / "INVALID"
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        with pytest.raises(FileBasedRoutingError):
            create_router_from_path(tmp_path)

    def test_catch_all_not_last_segment_raises_path_parse_error(
        self, tmp_path: Path, create_route_file
    ):
        """Catch-all parameter followed by another segment raises PathParseError."""
        # Create [...path]/extra/route.py - catch-all must be last
        catch_all_dir = tmp_path / "[...path]" / "extra"
        catch_all_dir.mkdir(parents=True)
        create_route_file(
            content="def get(): return {}",
            parent_dir=catch_all_dir,
        )

        with pytest.raises(PathParseError, match="Catch-all.*last"):
            create_router_from_path(tmp_path)

    def test_empty_bracket_segment_raises_path_parse_error(
        self, tmp_path: Path, create_route_file
    ):
        """Directory named '[]' (empty brackets) raises PathParseError."""
        invalid_dir = tmp_path / "[]"
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        with pytest.raises(PathParseError, match="Invalid path segment"):
            create_router_from_path(tmp_path)


class TestRouteValidationErrorInvalidExports:
    """RouteValidationError when route.py has invalid public exports."""

    def test_invalid_public_function_raises_route_validation_error(
        self, tmp_path: Path, create_route_file
    ):
        """Public function not in ALLOWED_HANDLERS raises RouteValidationError."""
        create_route_file(
            content="""
def get():
    return {"status": "ok"}

def compute_stats():
    return {"invalid": True}
""",
            parent_dir=tmp_path,
            subdir="analytics",
        )

        with pytest.raises(RouteValidationError, match="Invalid export"):
            create_router_from_path(tmp_path)

    def test_invalid_export_error_includes_function_name(
        self, tmp_path: Path, create_route_file
    ):
        """Error message names the invalid function so developer knows what to fix."""
        create_route_file(
            content="""
def get():
    return {}

def calculate_total():
    pass
""",
            parent_dir=tmp_path,
            subdir="items",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        assert "calculate_total" in str(exc_info.value)

    def test_invalid_export_error_suggests_underscore_prefix(
        self, tmp_path: Path, create_route_file
    ):
        """Error message suggests prefixing helper with underscore."""
        create_route_file(
            content="""
def get():
    return {}

def helper():
    pass
""",
            parent_dir=tmp_path,
            subdir="items",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "_helper" in error_message

    def test_invalid_export_error_includes_file_path(
        self, tmp_path: Path, create_route_file
    ):
        """Error message includes the file path for the offending route.py."""
        create_route_file(
            content="""
def get():
    return {}

def bad_export():
    pass
""",
            parent_dir=tmp_path,
            subdir="users",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "route.py" in error_message

    def test_invalid_export_error_lists_allowed_handlers(
        self, tmp_path: Path, create_route_file
    ):
        """Error message tells developer which handler names are valid."""
        create_route_file(
            content="""
def get():
    return {}

def fetch_data():
    pass
""",
            parent_dir=tmp_path,
            subdir="data",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "get" in error_message
        assert "post" in error_message

    def test_multiple_invalid_exports_listed_in_error(
        self, tmp_path: Path, create_route_file
    ):
        """Multiple invalid exports are all listed in the error message."""
        create_route_file(
            content="""
def get():
    return {}

def compute():
    pass

def transform():
    pass
""",
            parent_dir=tmp_path,
            subdir="pipeline",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "compute" in error_message
        assert "transform" in error_message

    def test_sync_websocket_handler_raises_route_validation_error(
        self, tmp_path: Path, create_route_file
    ):
        """Sync websocket handler raises RouteValidationError with helpful message."""
        create_route_file(
            content="""
def websocket(ws):
    pass
""",
            parent_dir=tmp_path,
            subdir="ws",
        )

        with pytest.raises(RouteValidationError, match="WebSocket handler must be async"):
            create_router_from_path(tmp_path)


class TestDuplicateRouteError:
    """DuplicateRouteError when two route files map to the same path+method."""

    def test_duplicate_path_and_method_raises_duplicate_route_error(
        self, tmp_path: Path, create_route_file
    ):
        """Two route.py files resolving to same path+method raise DuplicateRouteError."""
        # /users/route.py with GET
        create_route_file(
            content="def get(): return {'v': 1}",
            parent_dir=tmp_path,
            subdir="users",
        )

        # (group)/users/route.py also resolves to /users with GET
        create_route_file(
            content="def get(): return {'v': 2}",
            parent_dir=tmp_path,
            subdir="(admin)/users",
        )

        with pytest.raises(DuplicateRouteError, match="Duplicate route"):
            create_router_from_path(tmp_path)

    def test_duplicate_error_includes_method_and_path(
        self, tmp_path: Path, create_route_file
    ):
        """Error message includes both the HTTP method and path that conflict."""
        create_route_file(
            content="def post(): return {}",
            parent_dir=tmp_path,
            subdir="items",
        )

        create_route_file(
            content="def post(): return {}",
            parent_dir=tmp_path,
            subdir="(group)/items",
        )

        with pytest.raises(DuplicateRouteError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "POST" in error_message
        assert "/items" in error_message

    def test_duplicate_error_includes_both_file_paths(
        self, tmp_path: Path, create_route_file
    ):
        """Error message includes paths to both conflicting route.py files."""
        create_route_file(
            content="def get(): return {}",
            parent_dir=tmp_path,
            subdir="products",
        )

        create_route_file(
            content="def get(): return {}",
            parent_dir=tmp_path,
            subdir="(store)/products",
        )

        with pytest.raises(DuplicateRouteError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        # Both file paths should appear in the message
        assert "First" in error_message
        assert "Second" in error_message

    def test_duplicate_error_is_subclass_of_base_error(
        self, tmp_path: Path, create_route_file
    ):
        """DuplicateRouteError is catchable via FileBasedRoutingError base class."""
        create_route_file(
            content="def get(): return {}",
            parent_dir=tmp_path,
            subdir="api",
        )

        create_route_file(
            content="def get(): return {}",
            parent_dir=tmp_path,
            subdir="(v1)/api",
        )

        with pytest.raises(FileBasedRoutingError):
            create_router_from_path(tmp_path)

    def test_different_methods_same_path_do_not_conflict(
        self, tmp_path: Path, create_route_file
    ):
        """Same path with different methods should NOT raise DuplicateRouteError."""
        create_route_file(
            content="""
def get():
    return {"method": "GET"}

def post():
    return {"method": "POST"}

def put():
    return {"method": "PUT"}
""",
            parent_dir=tmp_path,
            subdir="resources",
        )

        # Should succeed without raising
        router = create_router_from_path(tmp_path)
        assert router is not None


class TestRouteValidationErrorSyntaxErrors:
    """RouteValidationError wrapping import/syntax errors in route.py."""

    def test_syntax_error_in_route_raises_route_validation_error(
        self, tmp_path: Path, create_route_file
    ):
        """Syntax error in route.py is wrapped in RouteValidationError."""
        create_route_file(
            content="def get(: return {}",
            parent_dir=tmp_path,
            subdir="broken",
        )

        with pytest.raises(RouteValidationError, match="Failed to import"):
            create_router_from_path(tmp_path)

    def test_syntax_error_includes_original_error_type(
        self, tmp_path: Path, create_route_file
    ):
        """Wrapped error includes the original exception type name."""
        create_route_file(
            content="def get(\n    invalid syntax here",
            parent_dir=tmp_path,
            subdir="syntax",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "SyntaxError" in error_message

    def test_syntax_error_includes_file_path(
        self, tmp_path: Path, create_route_file
    ):
        """Wrapped error includes the path to the offending route.py."""
        create_route_file(
            content="def get(: pass",
            parent_dir=tmp_path,
            subdir="bad-syntax",
        )

        # The directory name "bad-syntax" is valid for static segments
        # but the route.py has invalid Python
        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "route.py" in error_message

    def test_missing_import_in_route_raises_route_validation_error(
        self, tmp_path: Path, create_route_file
    ):
        """Missing import in route.py is wrapped in RouteValidationError."""
        create_route_file(
            content="""
import nonexistent_package_that_does_not_exist

def get():
    return nonexistent_package_that_does_not_exist.data()
""",
            parent_dir=tmp_path,
            subdir="missing-dep",
        )

        with pytest.raises(RouteValidationError, match="Failed to import"):
            create_router_from_path(tmp_path)

    def test_import_error_preserves_cause_chain(
        self, tmp_path: Path, create_route_file
    ):
        """The original exception is preserved as __cause__ for debugging."""
        create_route_file(
            content="import nonexistent_module_xyz",
            parent_dir=tmp_path,
            subdir="broken-import",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        assert exc_info.value.__cause__ is not None

    def test_runtime_error_in_module_raises_route_validation_error(
        self, tmp_path: Path, create_route_file
    ):
        """Runtime error during module execution is wrapped in RouteValidationError."""
        create_route_file(
            content="""
raise ValueError("Module-level initialization failed")

def get():
    return {}
""",
            parent_dir=tmp_path,
            subdir="runtime-error",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        error_message = str(exc_info.value)
        assert "ValueError" in error_message
        assert "initialization failed" in error_message


class TestErrorsRaisedAtStartup:
    """All errors are raised at router creation time, not during request handling.

    This is a critical design principle: fail fast, fail loud.
    Every error scenario tested above raises during create_router_from_path(),
    which runs at startup. This class adds explicit assertions about timing.
    """

    def test_invalid_export_fails_before_router_returned(
        self, tmp_path: Path, create_route_file
    ):
        """Invalid export causes failure DURING create_router_from_path, not after."""
        create_route_file(
            content="""
def get():
    return {}

def invalid_helper():
    pass
""",
            parent_dir=tmp_path,
            subdir="early-fail",
        )

        # The error must be raised BEFORE any router is returned.
        # If create_router_from_path completes, the test should fail.
        router = None
        with pytest.raises(RouteValidationError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created when validation fails"

    def test_duplicate_route_fails_before_router_returned(
        self, tmp_path: Path, create_route_file
    ):
        """Duplicate route causes failure DURING create_router_from_path, not after."""
        create_route_file(
            content="def get(): return {}",
            parent_dir=tmp_path,
            subdir="dup",
        )

        create_route_file(
            content="def get(): return {}",
            parent_dir=tmp_path,
            subdir="(alt)/dup",
        )

        router = None
        with pytest.raises(DuplicateRouteError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created when duplicates exist"

    def test_syntax_error_fails_before_router_returned(
        self, tmp_path: Path, create_route_file
    ):
        """Syntax error causes failure DURING create_router_from_path, not after."""
        create_route_file(
            content="def get( broken",
            parent_dir=tmp_path,
            subdir="syntax-fail",
        )

        router = None
        with pytest.raises(RouteValidationError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created when imports fail"

    def test_path_parse_error_fails_before_router_returned(
        self, tmp_path: Path, create_route_file
    ):
        """Invalid directory name causes failure DURING create_router_from_path."""
        invalid_dir = tmp_path / "UPPERCASE"
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        router = None
        with pytest.raises(PathParseError):
            router = create_router_from_path(tmp_path)

        assert router is None, "Router should not be created when parsing fails"


class TestErrorMessageQuality:
    """Error messages are descriptive and actionable.

    Developers should be able to read the error message and know
    exactly what to fix without needing to read source code.
    """

    def test_nonexistent_path_message_is_actionable(self, tmp_path: Path):
        """Error for nonexistent path tells developer the path and what happened."""
        target = tmp_path / "routes"

        with pytest.raises(RouteDiscoveryError) as exc_info:
            create_router_from_path(target)

        message = str(exc_info.value)
        # Must say what went wrong
        assert "does not exist" in message
        # Must include the path
        assert "routes" in message

    def test_not_directory_message_is_actionable(self, tmp_path: Path):
        """Error for file-as-directory tells developer it's not a directory."""
        target = tmp_path / "app.py"
        target.write_text("# not a directory")

        with pytest.raises(RouteDiscoveryError) as exc_info:
            create_router_from_path(target)

        message = str(exc_info.value)
        assert "not a directory" in message
        assert "app.py" in message

    def test_invalid_segment_message_lists_valid_formats(
        self, tmp_path: Path, create_route_file
    ):
        """Error for invalid segment explains valid naming formats."""
        invalid_dir = tmp_path / "Not-Valid!"
        invalid_dir.mkdir()
        create_route_file(
            content="def get(): return {}",
            parent_dir=invalid_dir,
        )

        with pytest.raises(PathParseError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Should reference valid formats
        assert "[param]" in message or "lowercase" in message

    def test_invalid_export_message_teaches_convention(
        self, tmp_path: Path, create_route_file
    ):
        """Error for invalid export teaches the naming convention."""
        create_route_file(
            content="""
def get():
    return {}

def process_data():
    pass
""",
            parent_dir=tmp_path,
            subdir="learn",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Should tell developer about the convention
        assert "process_data" in message
        assert "_process_data" in message  # underscore prefix suggestion
        assert "HTTP" in message or "verb" in message or "get" in message

    def test_duplicate_route_message_identifies_conflict(
        self, tmp_path: Path, create_route_file
    ):
        """Error for duplicate route identifies the exact conflict."""
        create_route_file(
            content="def delete(): return None",
            parent_dir=tmp_path,
            subdir="orders",
        )

        create_route_file(
            content="def delete(): return None",
            parent_dir=tmp_path,
            subdir="(shop)/orders",
        )

        with pytest.raises(DuplicateRouteError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Must identify the method and path
        assert "DELETE" in message
        assert "/orders" in message
        # Must reference both files
        assert "First" in message
        assert "Second" in message

    def test_syntax_error_message_includes_root_cause(
        self, tmp_path: Path, create_route_file
    ):
        """Error for syntax failure includes the root cause error type and detail."""
        create_route_file(
            content="def get(:\n    pass",
            parent_dir=tmp_path,
            subdir="cause",
        )

        with pytest.raises(RouteValidationError) as exc_info:
            create_router_from_path(tmp_path)

        message = str(exc_info.value)
        # Must include the original error type
        assert "SyntaxError" in message
        # Must reference the file
        assert "route.py" in message
