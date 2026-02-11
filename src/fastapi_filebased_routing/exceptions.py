"""Exception hierarchy for file-based routing errors."""


class FileBasedRoutingError(Exception):
    """Base exception for all file-based routing errors.

    This is the parent class for all exceptions raised by the
    fastapi-filebased-routing package. Catching this exception
    will catch all routing-related errors.

    Example:
        try:
            router = create_router_from_path("app")
        except FileBasedRoutingError as e:
            logger.error(f"Failed to create router: {e}")
    """


class PathParseError(FileBasedRoutingError):
    """Raised when a directory name has invalid syntax.

    This exception is raised during route scanning when a directory
    name doesn't conform to the expected path segment patterns.

    Examples of invalid syntax:
        - Missing closing bracket: [param
        - Multiple patterns in one segment: [...path][id]
        - Invalid parameter names: [123], [not-valid]

    Example:
        PathParseError("Invalid segment '[param': missing closing bracket")
    """


class RouteDiscoveryError(FileBasedRoutingError):
    """Raised when the base path doesn't exist or can't be scanned.

    This exception is raised when attempting to create a router from
    a directory that doesn't exist or isn't accessible.

    Example:
        RouteDiscoveryError("Base path '/app/routes' does not exist")
    """


class RouteValidationError(FileBasedRoutingError):
    """Raised for invalid exports, path traversal, or import errors.

    This exception is raised when a route.py file has invalid content:
        - Exports non-handler public functions (should be prefixed with _)
        - Contains path traversal attempts (..)
        - Has import errors or syntax errors
        - Invalid parameter names

    Example:
        RouteValidationError(
            "Invalid exports in /app/users/route.py: ['invalid_func']. "
            "Public functions must be HTTP method handlers or prefixed with '_'"
        )
    """


class DuplicateRouteError(FileBasedRoutingError):
    """Raised when two route files resolve to the same path+method.

    This exception is raised when multiple route.py files would
    register the same HTTP method on the same URL path.

    Example:
        DuplicateRouteError(
            "Duplicate route GET /users: "
            "/app/users/route.py conflicts with /app/api/users/route.py"
        )
    """


class RouteFilterError(FileBasedRoutingError):
    """Raised when route filter configuration is invalid.

    This exception is raised when:
        - Both include and exclude filters are provided simultaneously
        - Filter patterns are malformed

    Example:
        RouteFilterError(
            "Cannot specify both include and exclude filters: "
            "include=['users'], exclude=['admin']"
        )
    """


class MiddlewareValidationError(FileBasedRoutingError):
    """Raised when middleware configuration is invalid.

    This exception is raised when:
        - A _middleware.py file fails to import
        - A middleware attribute contains non-callable values
        - A class handler(route): block is misconfigured
        - Middleware is not async

    Example:
        MiddlewareValidationError(
            "Invalid middleware in _middleware.py: "
            "middleware list contains non-callable at index 2"
        )
    """
