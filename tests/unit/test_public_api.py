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


def test_internal_types_not_exported_at_root():
    """Internal pipeline types are NOT part of the public surface (sunset in 2.0.0).

    They remain importable from their internal ``core.*`` homes for advanced use,
    but the package root intentionally does not re-export them.
    """
    import fastapi_filebased_routing as m

    for name in (
        "ExtractedRoute",
        "PathSegment",
        "RouteDefinition",
        "RouteMetadata",
        "SegmentType",
    ):
        assert not hasattr(m, name), f"{name} should no longer be a public root export"


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
    """Route can be imported from root package (the sanctioned import surface)."""
    from fastapi_filebased_routing import Route
    from fastapi_filebased_routing.core.routes import Route as CoreRoute

    # Should be the same class
    assert Route is CoreRoute


def test_route_config_import_path():
    """RouteConfig can be imported from root package (the sanctioned import surface)."""
    from fastapi_filebased_routing import RouteConfig
    from fastapi_filebased_routing.core.routes import RouteConfig as CoreRouteConfig

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


# === Public-surface guard (pattern from httpx tests/test_exported_members.py) ===

_EXPECTED_EXPORTS = {
    "create_router_from_path",
    "dispatch",
    "Route",
    "RouteConfig",
    "DuplicateRouteError",
    "FileBasedRoutingError",
    "MiddlewareValidationError",
    "PathParseError",
    "RouteDiscoveryError",
    "RouteFilterError",
    "RouteValidationError",
}


def test_all_is_exactly_the_curated_set():
    """__all__ is locked to the intended public surface.

    Tripwire against accidentally widening (or shrinking) the public API. Adding
    a new export is a deliberate act that must update this set.
    """
    import fastapi_filebased_routing as m

    assert set(m.__all__) == _EXPECTED_EXPORTS


def test_no_internal_symbols_leak_at_package_root():
    """Every public top-level attribute is an export or a submodule — no stray internals.

    Guards the promise that ``core.*`` / ``adapter.*`` internals are not exposed
    accidentally at the package root.
    """
    import types

    import fastapi_filebased_routing as m

    public = {name for name in dir(m) if not name.startswith("_")}
    submodules = {name for name in public if isinstance(getattr(m, name), types.ModuleType)}
    leaked = public - set(m.__all__) - submodules
    assert leaked == set(), f"unexpected public symbols at package root: {sorted(leaked)}"


def test_exports_report_public_module_path():
    """Exported symbols report the public import path, not internal core.*/adapter.*.

    Keeps tracebacks, reprs, and generated docs honest about the sanctioned path.
    """
    import fastapi_filebased_routing as m

    for name in m.__all__:
        obj = getattr(m, name)
        assert obj.__module__ == "fastapi_filebased_routing", (
            f"{name}.__module__ leaks internal path {obj.__module__!r}"
        )
