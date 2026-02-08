"""FastAPI file-based routing plugin."""

# Primary API — the main entry point
# Core types — for advanced users and type checking
from fastapi_filebased_routing.core.importer import ExtractedRoute, RouteMetadata

# Middleware API (NEW in v0.2.0)
from fastapi_filebased_routing.core.middleware import RouteConfig, route
from fastapi_filebased_routing.core.parser import PathSegment, SegmentType
from fastapi_filebased_routing.core.scanner import RouteDefinition

# Exceptions — for error handling
from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    FileBasedRoutingError,
    MiddlewareValidationError,
    PathParseError,
    RouteDiscoveryError,
    RouteValidationError,
)
from fastapi_filebased_routing.fastapi.router import create_router_from_path

__all__ = [
    # Primary API
    "create_router_from_path",
    # Middleware API (NEW in v0.2.0)
    "route",
    "RouteConfig",
    # Core types
    "ExtractedRoute",
    "PathSegment",
    "RouteDefinition",
    "RouteMetadata",
    "SegmentType",
    # Exceptions
    "DuplicateRouteError",
    "FileBasedRoutingError",
    "MiddlewareValidationError",
    "PathParseError",
    "RouteDiscoveryError",
    "RouteValidationError",
]

__version__ = "1.0.0"
