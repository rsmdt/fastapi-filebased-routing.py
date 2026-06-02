"""Tests for public API exports in __init__.py."""


def test_primary_api_export():
    """create_router_from_path is exported from root package."""
    from fastapi_filebased_routing import create_router_from_path

    assert callable(create_router_from_path)


def test_middleware_api_exports():
    """Route and RouteConfig are exported (NEW in v0.2.0)."""
    from fastapi_filebased_routing import Route, RouteConfig

    assert Route is not None
    assert RouteConfig is not None


def test_route_is_plain_base_class():
    """Route is an ordinary base class for configured handlers (no metaclass)."""
    from fastapi_filebased_routing import Route

    # Route is a normal class — no custom metaclass intercepts subclassing
    assert isinstance(Route, type)
    assert type(Route) is type


def test_route_config_is_dataclass():
    """RouteConfig is the dataclass built from a Route subclass body."""
    from fastapi_filebased_routing import RouteConfig

    # RouteConfig should be a dataclass
    assert hasattr(RouteConfig, "__dataclass_fields__")
    assert "handler" in RouteConfig.__dataclass_fields__
    assert "middleware" in RouteConfig.__dataclass_fields__


def test_core_types_exported():
    """Core types are still exported (backward compatibility)."""
    from fastapi_filebased_routing import (
        ExtractedRoute,
        PathSegment,
        RouteDefinition,
        RouteMetadata,
        SegmentType,
    )

    assert ExtractedRoute is not None
    assert PathSegment is not None
    assert RouteDefinition is not None
    assert RouteMetadata is not None
    assert SegmentType is not None


def test_exceptions_exported():
    """All exceptions including MiddlewareValidationError and RouteFilterError are exported."""
    from fastapi_filebased_routing import (
        DuplicateRouteError,
        FileBasedRoutingError,
        MiddlewareValidationError,
        PathParseError,
        RouteDiscoveryError,
        RouteFilterError,
        RouteValidationError,
    )

    assert issubclass(DuplicateRouteError, FileBasedRoutingError)
    assert issubclass(PathParseError, FileBasedRoutingError)
    assert issubclass(RouteDiscoveryError, FileBasedRoutingError)
    assert issubclass(RouteValidationError, FileBasedRoutingError)
    assert issubclass(MiddlewareValidationError, FileBasedRoutingError)
    assert issubclass(RouteFilterError, FileBasedRoutingError)


def test_middleware_validation_error_is_new():
    """MiddlewareValidationError is the new exception in v0.2.0."""
    from fastapi_filebased_routing import (
        FileBasedRoutingError,
        MiddlewareValidationError,
    )

    # Should be a proper exception that can be raised
    error = MiddlewareValidationError("test error")
    assert isinstance(error, FileBasedRoutingError)
    assert str(error) == "test error"


def test_all_contains_new_exports():
    """__all__ includes new v0.2.0 and v1.2.0 exports."""
    import fastapi_filebased_routing

    assert "Route" in fastapi_filebased_routing.__all__
    assert "RouteConfig" in fastapi_filebased_routing.__all__
    assert "MiddlewareValidationError" in fastapi_filebased_routing.__all__
    assert "RouteFilterError" in fastapi_filebased_routing.__all__


def test_all_contains_existing_exports():
    """__all__ still includes v0.1.0 exports (backward compatibility)."""
    import fastapi_filebased_routing

    # Primary API
    assert "create_router_from_path" in fastapi_filebased_routing.__all__

    # Core types
    assert "ExtractedRoute" in fastapi_filebased_routing.__all__
    assert "PathSegment" in fastapi_filebased_routing.__all__
    assert "RouteDefinition" in fastapi_filebased_routing.__all__
    assert "RouteMetadata" in fastapi_filebased_routing.__all__
    assert "SegmentType" in fastapi_filebased_routing.__all__

    # Exceptions
    assert "DuplicateRouteError" in fastapi_filebased_routing.__all__
    assert "FileBasedRoutingError" in fastapi_filebased_routing.__all__
    assert "PathParseError" in fastapi_filebased_routing.__all__
    assert "RouteDiscoveryError" in fastapi_filebased_routing.__all__
    assert "RouteValidationError" in fastapi_filebased_routing.__all__


def test_version_is_2_0_0():
    """__version__ is bumped to 2.0.0 (Route class replaces the route metaclass)."""
    import fastapi_filebased_routing

    assert fastapi_filebased_routing.__version__ == "2.0.0"


def test_route_import_path():
    """Route can be imported from root package (not just core.middleware)."""
    from fastapi_filebased_routing import Route
    from fastapi_filebased_routing.core.middleware import Route as CoreRoute

    # Should be the same class
    assert Route is CoreRoute


def test_route_config_import_path():
    """RouteConfig can be imported from root package (not just core.middleware)."""
    from fastapi_filebased_routing import RouteConfig
    from fastapi_filebased_routing.core.middleware import RouteConfig as CoreRouteConfig

    # Should be the same class
    assert RouteConfig is CoreRouteConfig


def test_middleware_validation_error_import_path():
    """MiddlewareValidationError can be imported from root package."""
    from fastapi_filebased_routing import MiddlewareValidationError
    from fastapi_filebased_routing.exceptions import (
        MiddlewareValidationError as ExcMiddlewareValidationError,
    )

    # Should be the same class
    assert MiddlewareValidationError is ExcMiddlewareValidationError


def test_route_filter_error_import_path():
    """RouteFilterError can be imported from root package."""
    from fastapi_filebased_routing import RouteFilterError
    from fastapi_filebased_routing.exceptions import (
        RouteFilterError as ExcRouteFilterError,
    )

    # Should be the same class
    assert RouteFilterError is ExcRouteFilterError
