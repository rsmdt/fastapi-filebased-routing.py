"""FastAPI file-based routing plugin."""

# Primary API — the main entry point
# Core types — for advanced users and type checking
from fastapi_filebased_routing.core.importer import ExtractedRoute, RouteMetadata
from fastapi_filebased_routing.core.parser import PathSegment, SegmentType
from fastapi_filebased_routing.core.scanner import RouteDefinition

# Exceptions — for error handling
from fastapi_filebased_routing.exceptions import (
    DuplicateRouteError,
    FileBasedRoutingError,
    PathParseError,
    RouteDiscoveryError,
    RouteValidationError,
)
from fastapi_filebased_routing.fastapi.router import create_router_from_path

__all__ = [
    # Primary API
    "create_router_from_path",
    # Core types
    "ExtractedRoute",
    "PathSegment",
    "RouteDefinition",
    "RouteMetadata",
    "SegmentType",
    # Exceptions
    "DuplicateRouteError",
    "FileBasedRoutingError",
    "PathParseError",
    "RouteDiscoveryError",
    "RouteValidationError",
]

__version__ = "0.1.0"
