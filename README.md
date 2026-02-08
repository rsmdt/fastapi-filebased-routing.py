# fastapi-filebased-routing

Next.js-style file-based routing for FastAPI

[![PyPI version](https://img.shields.io/pypi/v/fastapi-filebased-routing.svg)](https://pypi.org/project/fastapi-filebased-routing/)
[![Python](https://img.shields.io/pypi/pyversions/fastapi-filebased-routing.svg)](https://pypi.org/project/fastapi-filebased-routing/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Define your API routes through directory structure and convention, not manual registration. Create a `route.py` file in a directory and it becomes an endpoint automatically. Say goodbye to router boilerplate and route registration conflicts.

## Installation

```bash
pip install fastapi-filebased-routing
```

## Quickstart

```python
from fastapi import FastAPI
from fastapi_filebased_routing import create_router_from_path

app = FastAPI()
app.include_router(create_router_from_path("app"))
```

That's it. Now every `route.py` file in your `app/` directory is automatically discovered and registered.

## Directory Convention Reference

Your directory structure defines your URL routes:

| Directory Name | URL Pattern | Example |
|---------------|-------------|---------|
| `users/` | `/users` | Static segment |
| `[id]/` | `/{id}` | Dynamic parameter |
| `[[version]]/` | Generates both `/` and `/{version}` | Optional parameter |
| `[...path]/` | `/{path:path}` | Catch-all (matches remaining segments) |
| `(admin)/` | Excluded from URL | Route group (organization only) |

### Examples

```
app/
├── users/                      # → /users
│   ├── route.py
│   └── [user_id]/              # → /users/{user_id}
│       └── route.py
├── api/
│   └── [[version]]/            # → /api and /api/{version}
│       └── users/
│           └── route.py
├── files/
│   └── [...path]/              # → /files/{path:path}
│       └── route.py
└── (admin)/                    # → /settings (group excluded)
    └── settings/
        └── route.py
```

## Route File Convention Reference

Each `route.py` file exports HTTP method handlers as functions:

### HTTP Methods

```python
# app/users/route.py
async def get():
    """List all users."""
    return {"users": []}

async def post(user: UserCreate):
    """Create a new user."""
    return {"id": "123", "name": user.name}  # Status 201 by convention

async def delete():
    """Delete all users."""
    return None  # Status 204 by convention
```

Supported methods: `get`, `post`, `put`, `patch`, `delete`, `head`, `options`

### WebSocket Handler

```python
# app/ws/chat/route.py
from fastapi import WebSocket

async def websocket(websocket: WebSocket):
    """WebSocket endpoint."""
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Echo: {data}")
```

### Dynamic Parameters

```python
# app/users/[user_id]/route.py
async def get(user_id: str):
    """Get user by ID."""
    return {"user_id": user_id}
```

Parameter names in directory brackets are automatically injected into your handlers.

### Metadata

Control OpenAPI documentation with module-level constants:

```python
# app/users/route.py
TAGS = ["users"]
SUMMARY = "User management endpoints"
DEPRECATED = True

async def get():
    """List all users."""
    return {"users": []}
```

If `TAGS` is not specified, tags are automatically derived from the first path segment.

### Private Helpers

Prefix functions with underscore to exclude them from route registration:

```python
# app/users/route.py
def _validate_email(email: str) -> bool:
    """Private helper — not registered as a route."""
    return "@" in email

async def post(email: str):
    """Create user."""
    if not _validate_email(email):
        raise ValueError("Invalid email")
    return {"email": email}
```

### Convention-Based Status Codes

Default HTTP status codes follow REST conventions:

- `POST` → 201 Created
- `DELETE` → 204 No Content
- All others → 200 OK

Override by returning a FastAPI `Response` with a custom status code, or use `status_code` in a `class handler(route):` block (see [Handler-Level Middleware](#handler-level-middleware)).

## Middleware

Three-layer middleware system that lets you scope cross-cutting concerns (auth, logging, rate limiting) to directories, files, or individual handlers. Middleware is validated at startup and assembled into chains with zero per-request overhead.

All middleware functions use the same signature:

```python
async def my_middleware(request, call_next):
    # Before handler
    response = await call_next(request)
    # After handler
    return response
```

Middleware must be `async`. Sync middleware raises a validation error at startup.

### Directory-Level Middleware

Create a `_middleware.py` file in any directory. Its middleware applies to all routes in that directory and all subdirectories.

```python
# app/api/_middleware.py — applies to all routes under /api/**
from app.auth import auth_required
from app.logging import request_logger

middleware = [auth_required, request_logger]
```

You can also define middleware inline as a single function:

```python
# app/_middleware.py — root-level timing middleware
import time

async def middleware(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Response-Time"] = f"{time.monotonic() - start:.4f}"
    return response
```

Directory middleware cascades: a `_middleware.py` in `app/` applies to every route, while one in `app/api/` only applies to routes under `/api/`. Parent middleware always runs before child middleware.

### File-Level Middleware

Add a `middleware` attribute at the top of any `route.py` to apply middleware to all handlers in that file.

```python
# app/api/users/route.py
from app.rate_limit import rate_limit

middleware = [rate_limit(100)]

async def get():
    """List users. Rate limited."""
    return {"users": []}

async def post(name: str):
    """Create user. Rate limited."""
    return {"name": name}
```

### Handler-Level Middleware

Use `class handler_name(route):` to attach middleware and metadata to a single handler. The `route` base class uses a metaclass that produces a callable `RouteConfig` instead of a class.

```python
# app/api/users/[user_id]/route.py
from fastapi_filebased_routing import route
from app.auth import require_role

# Simple handler — no handler-level middleware
async def get(user_id: str):
    return {"user_id": user_id}

# Configured handler — has its own middleware + metadata overrides
class delete(route):
    middleware = [require_role("admin")]
    status_code = 200  # Override convention-based 204

    async def handler(user_id: str):
        return {"deleted": user_id}
```

You can also define middleware inline as a single function directly in the block, without wrapping it in a list:

```python
# app/api/orders/route.py
from fastapi_filebased_routing import route

class post(route):
    async def middleware(request, call_next):
        if not request.headers.get("X-Idempotency-Key"):
            from fastapi.responses import JSONResponse
            return JSONResponse(
                {"error": "X-Idempotency-Key header required"},
                status_code=400,
            )
        return await call_next(request)

    async def handler(order: dict):
        """Create order. Requires idempotency key."""
        return {"order_id": "abc-123", **order}
```

Both styles coexist in the same file. Plain `async def` handlers and `class handler(route):` blocks can be mixed freely.

The `class handler(route):` block supports these attributes:

| Attribute | Type | Description |
|-----------|------|-------------|
| `handler` | `async def` | **Required.** The handler function. |
| `middleware` | `list` or single callable | Middleware for this handler only. |
| `tags` | `list[str]` | Override OpenAPI tags. |
| `summary` | `str` | Override OpenAPI summary. |
| `deprecated` | `bool` | Mark handler as deprecated. |
| `status_code` | `int` | Override default HTTP status code. |

### Execution Order

When a request hits a route with middleware at multiple levels, they execute in this order:

```
Directory middleware (root → leaf)
  → File-level middleware
    → Handler-level middleware
      → Handler function
    ← Handler-level middleware
  ← File-level middleware
← Directory middleware
```

Each middleware can modify the request before calling `call_next`, and modify the response after. Middleware can also short-circuit by returning a response without calling `call_next`:

```python
async def auth_guard(request, call_next):
    if not request.headers.get("Authorization"):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)
```

### Middleware Example Structure

```
app/
├── _middleware.py              # Timing middleware for ALL routes
├── health/
│   └── route.py                # No middleware (health check)
├── api/
│   ├── _middleware.py           # Auth middleware for /api/**
│   └── users/
│       ├── route.py             # middleware = [rate_limit(100)]
│       └── [user_id]/
│           └── route.py         # class delete(route): middleware = [require_role("admin")]
└── (admin)/
    ├── _middleware.py           # Admin auth (group excluded from URL)
    └── settings/
        └── route.py             # Inherits admin middleware → /settings
```

## Complete Example

```
app/
├── _middleware.py                # Request timing for all routes
├── health/
│   └── route.py
├── api/
│   ├── _middleware.py            # Auth for all /api/** routes
│   └── users/
│       ├── route.py              # File-level rate limiting
│       └── [user_id]/
│           └── route.py          # Handler-level admin guard
└── ws/
    └── chat/
        └── route.py
```

```python
# app/_middleware.py — applies to every route
import time

async def middleware(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Response-Time"] = f"{time.monotonic() - start:.4f}"
    return response
```

```python
# app/api/_middleware.py — applies to /api/** routes only
async def auth_required(request, call_next):
    if not request.headers.get("Authorization"):
        from fastapi.responses import JSONResponse
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    return await call_next(request)

middleware = [auth_required]
```

```python
# app/health/route.py — inherits only root timing middleware
async def get():
    """Health check endpoint."""
    return {"status": "ok"}
```

```python
# app/api/users/route.py — inherits root timing + API auth middleware
from pydantic import BaseModel

class User(BaseModel):
    id: str
    name: str

TAGS = ["users"]

async def rate_limit(request, call_next):
    # Simple rate limiting middleware
    return await call_next(request)

middleware = [rate_limit]

async def get() -> list[User]:
    """List all users."""
    return [User(id="1", name="Alice")]

async def post(name: str) -> User:
    """Create a new user."""
    return User(id="2", name=name)
```

```python
# app/api/users/[user_id]/route.py — handler-level middleware
from fastapi_filebased_routing import route

TAGS = ["users"]

async def get(user_id: str):
    """Get user by ID."""
    return {"user_id": user_id, "name": "Alice"}

class delete(route):
    """Delete requires admin role."""
    middleware = [lambda request, call_next: call_next(request)]  # your admin check
    status_code = 200

    async def handler(user_id: str):
        """Delete user by ID."""
        return {"deleted": user_id}
```

```python
# app/ws/chat/route.py
from fastapi import WebSocket

async def websocket(websocket: WebSocket):
    """WebSocket chat endpoint."""
    await websocket.accept()
    while True:
        message = await websocket.receive_text()
        await websocket.send_text(f"Echo: {message}")
```

```python
# main.py
from fastapi import FastAPI
from fastapi_filebased_routing import create_router_from_path

app = FastAPI(title="My API")
app.include_router(create_router_from_path("app"))

# Run with: uvicorn main:app --reload
```

Visit `http://localhost:8000/docs` to see your auto-generated OpenAPI documentation with all routes organized by tags.

## API Reference

### `create_router_from_path`

```python
def create_router_from_path(
    base_path: str | Path,
    *,
    prefix: str = "",
) -> APIRouter
```

Create a FastAPI APIRouter from a directory of `route.py` files.

**Parameters:**
- `base_path` (str | Path): Root directory containing route.py files
- `prefix` (str, optional): URL prefix for all discovered routes (default: "")

**Returns:**
- `APIRouter`: A FastAPI router with all discovered routes registered

**Raises:**
- `RouteDiscoveryError`: If base_path doesn't exist or isn't a directory
- `RouteValidationError`: If a route file has invalid exports or parameters
- `DuplicateRouteError`: If two route files resolve to the same path+method
- `PathParseError`: If a directory name has invalid syntax
- `MiddlewareValidationError`: If a `_middleware.py` file fails to import or contains invalid middleware

**Example:**

```python
from fastapi import FastAPI
from fastapi_filebased_routing import create_router_from_path

app = FastAPI()

# Basic usage
app.include_router(create_router_from_path("app"))

# With prefix
app.include_router(create_router_from_path("app", prefix="/api/v1"))

# Multiple routers
app.include_router(create_router_from_path("app/public"))
app.include_router(create_router_from_path("app/admin", prefix="/admin"))
```

### `route`

Base class for handler-level middleware and metadata configuration. Uses a metaclass that returns a `RouteConfig` instead of a class.

```python
from fastapi_filebased_routing import route

class get(route):
    middleware = [auth_required]
    tags = ["users"]
    summary = "Get user details"

    async def handler(user_id: str):
        return {"user_id": user_id}

# `get` is now a RouteConfig, not a class
# `get(user_id="123")` calls the handler directly
```

### `RouteConfig`

Frozen dataclass produced by `class handler(route):` blocks. Holds the handler function, middleware, and metadata overrides. Callable — delegates to the wrapped handler.

```python
from fastapi_filebased_routing import RouteConfig

# RouteConfig is typically created via the route metaclass, not directly
# Available for type checking and isinstance() checks
```

**Attributes:**
- `handler` (Callable): The handler function
- `middleware` (tuple): Middleware callables
- `tags` (tuple[str, ...] | None): OpenAPI tags override
- `summary` (str | None): OpenAPI summary override
- `deprecated` (bool): Whether the handler is deprecated
- `status_code` (int | None): HTTP status code override

## Features

- Zero-configuration route discovery
- Three-layer middleware system (directory, file, handler) with cascading inheritance
- `class handler(route):` block syntax for per-handler middleware and metadata
- Middleware validated at startup with zero per-request overhead for routes without middleware
- Next.js feature parity (dynamic params, optional params, catch-all, route groups)
- Battle-tested security (path traversal protection, symlink validation)
- Convention over configuration (status codes, tags, metadata)
- WebSocket support
- Sync and async handlers
- Works with FastAPI's existing routing (coexists with manual routes)
- Hot reload compatible (uvicorn --reload works out of the box)
- Type-safe with full mypy strict mode support

## Why This Plugin?

FastAPI developers building medium-to-large APIs face these problems:

1. **Manual route registration is tedious.** Every endpoint requires updating a centralized router file.
2. **Route discoverability degrades.** Finding the handler for `/api/v1/users/{id}` requires searching across files.
3. **Middleware wiring is repetitive.** Applying auth to 20 admin endpoints means 20 copies of `Depends(require_admin)`.
4. **Full-stack developers experience friction.** Next.js has file-based routing, FastAPI requires manual wiring.

This plugin solves all four by bringing file-based routing and hierarchical middleware to FastAPI. Create a `_middleware.py` file in a directory and every route underneath inherits it automatically.

### Comparison with Alternatives

| Feature | fastapi-filebased-routing | fastapi-file-router | runapi |
|---------|--------------------------|---------------------|--------|
| Dynamic params `[id]` | ✅ | ✅ | ✅ |
| Optional params `[[version]]` | ✅ | ❌ | ❌ |
| Catch-all `[...path]` | ✅ | ❌ | ❌ |
| Route groups `(name)` | ✅ | ❌ | ❌ |
| Directory middleware | ✅ Cascading inheritance | ❌ | ❌ |
| File-level middleware | ✅ | ❌ | ❌ |
| Handler-level middleware | ✅ Block syntax | ❌ | ❌ |
| WebSocket support | ✅ | ❌ | ❌ |
| Security validation | ✅ Enterprise | ⚠️ Basic | ⚠️ Basic |
| Type safety (mypy strict) | ✅ | ❌ | ❌ |
| Production ready | ✅ | ⚠️ | ⚠️ |

## Requirements

- Python 3.13+
- FastAPI 0.115.0+

## License

MIT License - see LICENSE file for details.

## Contributing

This plugin is extracted from a production codebase and is actively maintained. Issues, feature requests, and pull requests are welcome.

GitHub: https://github.com/irudi/fastapi-filebased-routing
