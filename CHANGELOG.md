# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.0]

### Changed (BREAKING)

- Replaced the `route` metaclass with a plain `Route` base class. Declare handlers as `class VERB(Route):` (uppercase HTTP verb); the subclass stays a real class and is now correctly typed.

### Removed

- The `route` symbol and `_RouteMeta` metaclass. Use `Route` instead; other exports are unchanged.

### Migration

- Change the import from `route` to `Route` and rename `class <verb>(route):` to `class <VERB>(Route):`. Optionally mark `handler` as `@staticmethod`.

## [1.2.1]

### Fixed

- Scanner no longer rejects routes when the project lives under a dotfile-prefixed ancestor (e.g. running from a git worktree at `.worktree/main`, or a project nested under `.venvs/`). Dotfile filtering now applies only to components under the scan base, not to incidental ancestors of the absolute path.

## [1.2.0]

### Added

- **`include` and `exclude` parameters** on `create_router_from_path()` for route-level filtering, supporting both glob patterns (via `fnmatch`) and bare segment names. Bare names match any segment in the path, making route groups transparent.
- **`core/filter.py`** module — filters routes and middleware before any imports, so excluded code never enters memory. Enables module monolith deployment topologies (e.g. DMZ instances loading only public routes, admin code never imported).
- Middleware files (`_middleware.py`) are filtered alongside their routes — only ancestors of surviving routes are retained.
- **`RouteFilterError`** exception, raised when both `include` and `exclude` are supplied (mutually exclusive).

### Changed

- Public API surface expanded to export `RouteFilterError` and the filtering parameters.

## [1.1.0]

### Added

- **`dispatch()` adapter** for class-based middleware — allows reusing existing `BaseHTTPMiddleware`-style classes in `_middleware.py` files without rewriting them as functions.
- Public export: `from fastapi_filebased_routing import dispatch`.
- Documentation and examples for the dispatch pattern in README.

## [1.0.2]

### Changed

- Widened version compatibility: now supports **Python 3.10+** (previously 3.11+) and **FastAPI 0.65.0+** (previously >=0.100).
- CI matrix expanded to validate the widened compatibility range (Python 3.10/3.14 × FastAPI 0.65.0/latest).

## [1.0.1]

### Changed

- Switched build backend from `hatchling` to **`uv_build`** for tighter integration with the `uv` toolchain.
- Updated repository URLs to `github.com/rsmdt/fastapi-filebased-routing.py`.

## [1.0.0]

First stable release. The public API is now covered by semantic versioning guarantees.

### Added

- GitHub Actions: CI workflow and tag-triggered PyPI publish workflow.
- Concurrency integration tests verifying request isolation, auth short-circuit, POST body isolation, and error routing under 50 concurrent requests with random delays.
- Pre-commit hooks for `ruff check`, `ruff format`, and `mypy`.

### Changed

- README restructured for clarity and compactness (438 lines → 97 lines).
- API stabilized — backward-compatibility guarantees apply from this release forward.

## [0.2.0]

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

## [0.1.0]

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

[1.2.1]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v1.2.1
[1.2.0]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v1.2.0
[1.1.0]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v1.1.0
[1.0.2]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v1.0.2
[1.0.1]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v1.0.1
[1.0.0]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v1.0.0
[0.2.0]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v0.2.0
[0.1.0]: https://github.com/rsmdt/fastapi-filebased-routing.py/releases/tag/v0.1.0
