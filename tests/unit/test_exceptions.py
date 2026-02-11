"""Unit tests for exception hierarchy."""

import pytest

from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    FileBasedRoutingError,
    MiddlewareValidationError,
    PathParseError,
    RouteDiscoveryError,
    RouteFilterError,
    RouteValidationError,
)


class TestFileBasedRoutingError:
    """Tests for the base exception class."""

    def test_inherits_from_exception(self) -> None:
        """FileBasedRoutingError inherits from Exception."""
        assert issubclass(FileBasedRoutingError, Exception)

    def test_can_be_raised_with_message(self) -> None:
        """FileBasedRoutingError can be raised with a descriptive message."""
        with pytest.raises(FileBasedRoutingError, match="test error message"):
            raise FileBasedRoutingError("test error message")

    def test_can_be_caught_as_base_exception(self) -> None:
        """FileBasedRoutingError can be caught as Exception."""
        try:
            raise FileBasedRoutingError("test error")
        except Exception as e:
            assert isinstance(e, FileBasedRoutingError)

    def test_message_is_preserved(self) -> None:
        """Exception message is accessible."""
        error = FileBasedRoutingError("specific error details")
        assert str(error) == "specific error details"


class TestPathParseError:
    """Tests for path parsing errors."""

    def test_inherits_from_file_based_routing_error(self) -> None:
        """PathParseError inherits from FileBasedRoutingError."""
        assert issubclass(PathParseError, FileBasedRoutingError)

    def test_can_be_raised_with_message(self) -> None:
        """PathParseError can be raised with a descriptive message."""
        with pytest.raises(PathParseError, match="invalid directory name"):
            raise PathParseError("invalid directory name")

    def test_can_be_caught_with_base_class(self) -> None:
        """PathParseError can be caught as FileBasedRoutingError."""
        try:
            raise PathParseError("invalid syntax in segment")
        except FileBasedRoutingError as e:
            assert isinstance(e, PathParseError)

    def test_message_with_context(self) -> None:
        """PathParseError can carry detailed context."""
        error = PathParseError("Invalid segment '[': missing closing bracket")
        assert "Invalid segment" in str(error)
        assert "missing closing bracket" in str(error)


class TestRouteDiscoveryError:
    """Tests for route discovery errors."""

    def test_inherits_from_file_based_routing_error(self) -> None:
        """RouteDiscoveryError inherits from FileBasedRoutingError."""
        assert issubclass(RouteDiscoveryError, FileBasedRoutingError)

    def test_can_be_raised_with_message(self) -> None:
        """RouteDiscoveryError can be raised with a descriptive message."""
        with pytest.raises(RouteDiscoveryError, match="base path not found"):
            raise RouteDiscoveryError("base path not found")

    def test_can_be_caught_with_base_class(self) -> None:
        """RouteDiscoveryError can be caught as FileBasedRoutingError."""
        try:
            raise RouteDiscoveryError("directory does not exist")
        except FileBasedRoutingError as e:
            assert isinstance(e, RouteDiscoveryError)

    def test_message_with_path_context(self) -> None:
        """RouteDiscoveryError can include file path context."""
        error = RouteDiscoveryError("Base path '/app/routes' is not a directory")
        assert "/app/routes" in str(error)
        assert "not a directory" in str(error)


class TestRouteValidationError:
    """Tests for route validation errors."""

    def test_inherits_from_file_based_routing_error(self) -> None:
        """RouteValidationError inherits from FileBasedRoutingError."""
        assert issubclass(RouteValidationError, FileBasedRoutingError)

    def test_can_be_raised_with_message(self) -> None:
        """RouteValidationError can be raised with a descriptive message."""
        with pytest.raises(RouteValidationError, match="invalid exports"):
            raise RouteValidationError("invalid exports")

    def test_can_be_caught_with_base_class(self) -> None:
        """RouteValidationError can be caught as FileBasedRoutingError."""
        try:
            raise RouteValidationError("path traversal detected")
        except FileBasedRoutingError as e:
            assert isinstance(e, RouteValidationError)

    def test_message_with_file_and_export_context(self) -> None:
        """RouteValidationError can include file path and export details."""
        error = RouteValidationError("Invalid exports in /app/users/route.py: ['invalid_func']")
        assert "/app/users/route.py" in str(error)
        assert "invalid_func" in str(error)


class TestDuplicateRouteError:
    """Tests for duplicate route errors."""

    def test_inherits_from_file_based_routing_error(self) -> None:
        """DuplicateRouteError inherits from FileBasedRoutingError."""
        assert issubclass(DuplicateRouteError, FileBasedRoutingError)

    def test_can_be_raised_with_message(self) -> None:
        """DuplicateRouteError can be raised with a descriptive message."""
        with pytest.raises(DuplicateRouteError, match="duplicate route"):
            raise DuplicateRouteError("duplicate route")

    def test_can_be_caught_with_base_class(self) -> None:
        """DuplicateRouteError can be caught as FileBasedRoutingError."""
        try:
            raise DuplicateRouteError("route already exists")
        except FileBasedRoutingError as e:
            assert isinstance(e, DuplicateRouteError)

    def test_message_with_conflicting_files(self) -> None:
        """DuplicateRouteError can include both conflicting file paths."""
        error = DuplicateRouteError(
            "Duplicate route GET /users: /app/users/route.py conflicts with /app/api/users/route.py"
        )
        assert "GET /users" in str(error)
        assert "/app/users/route.py" in str(error)
        assert "/app/api/users/route.py" in str(error)


class TestExceptionImports:
    """Tests for exception import paths."""

    def test_all_exceptions_importable_from_main_module(self) -> None:
        """All exceptions can be imported from fastapi_filebased_routing."""
        # This test verifies that __init__.py properly re-exports exceptions
        from fastapi_filebased_routing import (
            DuplicateRouteError as ImportedDuplicate,
        )
        from fastapi_filebased_routing import PathParseError as ImportedPathParse
        from fastapi_filebased_routing import (
            RouteDiscoveryError as ImportedDiscovery,
        )
        from fastapi_filebased_routing import (
            RouteValidationError as ImportedValidation,
        )

        assert ImportedDuplicate is DuplicateRouteError
        assert ImportedPathParse is PathParseError
        assert ImportedDiscovery is RouteDiscoveryError
        assert ImportedValidation is RouteValidationError

        # MiddlewareValidationError will be exported in Phase 4 (not yet in v0.1.0)
        # For now, it can only be imported directly from the exceptions module

    def test_base_exception_importable_from_main_module(self) -> None:
        """Base exception can be imported from fastapi_filebased_routing."""
        from fastapi_filebased_routing import (
            FileBasedRoutingError as ImportedBase,
        )

        assert ImportedBase is FileBasedRoutingError

    def test_exceptions_importable_from_exceptions_module(self) -> None:
        """All exceptions can be imported from exceptions submodule."""
        from fastapi_filebased_routing.exceptions import (
            DuplicateRouteError as DirectDuplicate,
        )
        from fastapi_filebased_routing.exceptions import (
            FileBasedRoutingError as DirectBase,
        )
        from fastapi_filebased_routing.exceptions import (
            MiddlewareValidationError as DirectMiddleware,
        )
        from fastapi_filebased_routing.exceptions import (
            PathParseError as DirectPathParse,
        )
        from fastapi_filebased_routing.exceptions import (
            RouteDiscoveryError as DirectDiscovery,
        )
        from fastapi_filebased_routing.exceptions import (
            RouteValidationError as DirectValidation,
        )

        assert DirectDuplicate is DuplicateRouteError
        assert DirectBase is FileBasedRoutingError
        assert DirectMiddleware is MiddlewareValidationError
        assert DirectPathParse is PathParseError
        assert DirectDiscovery is RouteDiscoveryError
        assert DirectValidation is RouteValidationError


class TestMiddlewareValidationError:
    """Tests for middleware validation errors."""

    def test_inherits_from_file_based_routing_error(self) -> None:
        """MiddlewareValidationError inherits from FileBasedRoutingError."""
        assert issubclass(MiddlewareValidationError, FileBasedRoutingError)

    def test_can_be_raised_with_message(self) -> None:
        """MiddlewareValidationError can be raised with a descriptive message."""
        with pytest.raises(MiddlewareValidationError, match="invalid middleware"):
            raise MiddlewareValidationError("invalid middleware")

    def test_can_be_caught_with_base_class(self) -> None:
        """MiddlewareValidationError can be caught as FileBasedRoutingError."""
        try:
            raise MiddlewareValidationError("middleware not callable")
        except FileBasedRoutingError as e:
            assert isinstance(e, MiddlewareValidationError)

    def test_message_with_middleware_context(self) -> None:
        """MiddlewareValidationError can include middleware details."""
        error = MiddlewareValidationError(
            "Invalid middleware in _middleware.py: middleware list contains non-callable at index 2"
        )
        assert "_middleware.py" in str(error)
        assert "non-callable" in str(error)
        assert "index 2" in str(error)


class TestRouteFilterError:
    """Tests for route filter errors."""

    def test_inherits_from_file_based_routing_error(self) -> None:
        """RouteFilterError inherits from FileBasedRoutingError."""
        assert issubclass(RouteFilterError, FileBasedRoutingError)

    def test_can_be_raised_with_message(self) -> None:
        """RouteFilterError can be raised with a descriptive message."""
        with pytest.raises(RouteFilterError, match="invalid filter"):
            raise RouteFilterError("invalid filter")

    def test_can_be_caught_with_base_class(self) -> None:
        """RouteFilterError can be caught as FileBasedRoutingError."""
        try:
            raise RouteFilterError("both include and exclude provided")
        except FileBasedRoutingError as e:
            assert isinstance(e, RouteFilterError)

    def test_message_with_filter_context(self) -> None:
        """RouteFilterError can include filter configuration details."""
        error = RouteFilterError(
            "Cannot specify both include and exclude filters: include=['users'], exclude=['admin']"
        )
        assert "include" in str(error)
        assert "exclude" in str(error)


class TestExceptionHierarchy:
    """Tests for exception hierarchy behavior."""

    def test_catch_all_routing_errors_with_base_class(self) -> None:
        """FileBasedRoutingError catches all routing-related exceptions."""
        exceptions_to_test = [
            PathParseError("test"),
            RouteDiscoveryError("test"),
            RouteValidationError("test"),
            DuplicateRouteError("test"),
            MiddlewareValidationError("test"),
            RouteFilterError("test"),
        ]

        for exc in exceptions_to_test:
            try:
                raise exc
            except FileBasedRoutingError as e:
                assert isinstance(e, type(exc))
            else:
                pytest.fail(f"{type(exc).__name__} was not caught by FileBasedRoutingError")

    def test_each_exception_is_distinct(self) -> None:
        """Each exception class is a distinct type."""
        assert PathParseError is not RouteDiscoveryError
        assert RouteDiscoveryError is not RouteValidationError
        assert RouteValidationError is not DuplicateRouteError
        assert DuplicateRouteError is not MiddlewareValidationError
        assert MiddlewareValidationError is not RouteFilterError
        assert RouteFilterError is not PathParseError

    def test_exception_type_checking(self) -> None:
        """Exception instances can be type-checked correctly."""
        path_error = PathParseError("test")
        discovery_error = RouteDiscoveryError("test")
        validation_error = RouteValidationError("test")
        duplicate_error = DuplicateRouteError("test")
        middleware_error = MiddlewareValidationError("test")
        filter_error = RouteFilterError("test")

        assert isinstance(path_error, PathParseError)
        assert not isinstance(path_error, RouteDiscoveryError)

        assert isinstance(discovery_error, RouteDiscoveryError)
        assert not isinstance(discovery_error, RouteValidationError)

        assert isinstance(validation_error, RouteValidationError)
        assert not isinstance(validation_error, DuplicateRouteError)

        assert isinstance(duplicate_error, DuplicateRouteError)
        assert not isinstance(duplicate_error, MiddlewareValidationError)

        assert isinstance(middleware_error, MiddlewareValidationError)
        assert not isinstance(middleware_error, RouteFilterError)

        assert isinstance(filter_error, RouteFilterError)
        assert not isinstance(filter_error, PathParseError)

        # All should be instances of the base class
        assert isinstance(path_error, FileBasedRoutingError)
        assert isinstance(discovery_error, FileBasedRoutingError)
        assert isinstance(validation_error, FileBasedRoutingError)
        assert isinstance(duplicate_error, FileBasedRoutingError)
        assert isinstance(middleware_error, FileBasedRoutingError)
        assert isinstance(filter_error, FileBasedRoutingError)
