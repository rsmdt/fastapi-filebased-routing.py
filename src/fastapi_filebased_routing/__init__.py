"""FastAPI file-based routing plugin.

Public package facade. This module is the only sanctioned import surface; deep
paths (``core.*``, ``adapter.*``) are internal and unstable.
"""

from fastapi_filebased_routing.adapter.router_factory import create_router_from_path
from fastapi_filebased_routing.core.discovery import RouteDefinition
from fastapi_filebased_routing.core.dispatch import dispatch
from fastapi_filebased_routing.core.handlers import ExtractedRoute, RouteMetadata
from fastapi_filebased_routing.core.paths import PathSegment, SegmentType
from fastapi_filebased_routing.core.routes import Route, RouteConfig
from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    FileBasedRoutingError,
    MiddlewareValidationError,
    PathParseError,
    RouteDiscoveryError,
    RouteFilterError,
    RouteValidationError,
)

__all__ = [
    # Primary API
    "create_router_from_path",
    # Middleware API
    "dispatch",
    "Route",
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
    "RouteFilterError",
    "RouteValidationError",
]

__version__ = "2.0.0"
