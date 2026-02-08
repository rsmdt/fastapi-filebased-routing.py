# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/irudi/fastapi-filebased-routing/compare/main...main
