"""FastAPI file-based routing plugin.

Public package facade. This module is the only sanctioned import surface; deep
paths (``core.*``, ``adapter.*``) are internal and unstable.
"""

import contextlib

from fastapi_filebased_routing.adapter.router_factory import create_router_from_path
from fastapi_filebased_routing.core.dispatch import dispatch
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

# Report the public import path on exported symbols so tracebacks, reprs, and
# generated docs show ``fastapi_filebased_routing`` rather than the internal
# ``core.*`` / ``adapter.*`` paths (which are unstable). Mirrors httpx.
for _name in __all__:
    with contextlib.suppress(AttributeError, TypeError):
        globals()[_name].__module__ = __name__
del _name, contextlib
