# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-02-08

### Added

- **Directory-level middleware** via `_middleware.py` files — applies to all routes in the directory subtree
- **File-level middleware** via `middleware = [...]` at module level in `route.py` — applies to all handlers in the file
- **Handler-level middleware** via `class handler(route):` syntax with `middleware = [...]` — per-handler configuration
- **Three-layer middleware execution order**: directory (parent→child) → file → handler
- **`route` base class** with metaclass that returns `RouteConfig` — `class get(route):` returns callable config, not a class
- **`RouteConfig` dataclass** — carries handler, middleware, and metadata (tags, summary, deprecated, status_code)
- **`build_middleware_chain()`** — composable middleware chain with `call_next` semantics
- **`_make_middleware_route()`** — custom APIRoute subclass preserving FastAPI dependency injection
- **`MiddlewareValidationError`** exception for middleware configuration issues
- **Middleware context enrichment** — middleware can set `request.state` values visible to subsequent middleware and handlers
- **Middleware short-circuit** — middleware can return response without calling `call_next`
- **Startup-time validation** — all middleware validated when `create_router_from_path()` is called
- **Handler-level metadata override** — `class handler(route):` can set `tags`, `summary`, `deprecated`, `status_code`
- `examples/middleware/` — comprehensive example showing all middleware features

### Changed

- Bumped version to 0.2.0

### Fixed

- N/A

## [0.1.0] - 2025-10-01

### Added

- Automatic route discovery from directory structure with `create_router_from_path()`
- HTTP method handlers: GET, POST, PUT, PATCH, DELETE, HEAD, OPTIONS
- WebSocket handler support via `async def websocket(ws: WebSocket)` convention
- Dynamic path parameters using `[param]` directory syntax
- Optional path parameters using `[[param]]` directory syntax with automatic variant generation
- Catch-all path parameters using `[...param]` directory syntax for arbitrary nested paths
- Route groups using `(group)` directory syntax for code organization without URL impact
- Convention-based status codes (POST→201, DELETE→204, others→200)
- Route metadata support: TAGS, SUMMARY, DEPRECATED constants in route files
- Automatic tag derivation from path segments (skipping api/version prefixes)
- Security validation for path traversal attempts
- Symlink validation to prevent directory traversal attacks
- Parameter name validation (must be valid Python identifiers)
- Duplicate route detection with detailed error reporting
- Sync and async handler support (both `def` and `async def`)
- Full FastAPI APIRouter integration for seamless coexistence with manual routes
- Router prefix support via `prefix` parameter
- Type-safe with PEP 561 marker
- 98%+ test coverage across all modules

[Unreleased]: https://github.com/irudi/fastapi-filebased-routing/compare/v0.2.0...main
[0.2.0]: https://github.com/irudi/fastapi-filebased-routing/releases/tag/v0.2.0
[0.1.0]: https://github.com/irudi/fastapi-filebased-routing/releases/tag/v0.1.0
