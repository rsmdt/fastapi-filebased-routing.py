# fastapi-filebased-routing

Next.js-style file-based routing for FastAPI

[![PyPI version](https://img.shields.io/pypi/v/fastapi-filebased-routing.svg)](https://pypi.org/project/fastapi-filebased-routing/)
[![Python](https://img.shields.io/pypi/pyversions/fastapi-filebased-routing.svg)](https://pypi.org/project/fastapi-filebased-routing/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Define your API routes through directory structure and convention, not manual registration. Create a `route.py` file in a directory and it becomes an endpoint automatically. Say goodbye to router boilerplate and route registration conflicts.

## Table of Contents

- [🚀 Installation & Quickstart](#-installation--quickstart)
- [📁 File-Based Routing Explained](#-file-based-routing-explained)
- [📍 Route Handlers](#-route-handlers)
- [🔗 Middleware](#-middleware)
- [📦 Examples](#-examples)
- [📖 API Reference](#-api-reference)
- [💡 Why This Plugin?](#-why-this-plugin)
- [🤝 Contributing](#-contributing)

## 🚀 Installation & Quickstart

Requires **Python 3.13+** and **FastAPI 0.115.0+**.

```bash
pip install fastapi-filebased-routing
```

```python
from fastapi import FastAPI
from fastapi_filebased_routing import create_router_from_path

app = FastAPI()
app.include_router(create_router_from_path("app"))
```

That's it. Every `route.py` file in your `app/` directory is automatically discovered and registered.

## 📁 File-Based Routing Explained

Your directory structure defines your URL routes. Given `create_router_from_path("app")`:

```
app/
├── _middleware.py                  # directory middleware → ALL routes
├── health/
│   └── route.py                   # get → /health
├── api/
│   ├── _middleware.py             # directory middleware → /api/**
│   ├── [[version]]/
│   │   └── route.py              # → /api and /api/{version}
│   └── users/
│       ├── route.py              # file-level middleware + handlers
│       └── [user_id]/
│           └── route.py          # handler-level middleware via class
├── files/
│   └── [...path]/
│       └── route.py              # catch-all route
├── ws/
│   └── chat/
│       └── route.py              # websocket handler
└── (admin)/                       # group: excluded from URL
    ├── _middleware.py             # directory middleware → /settings/**
    └── settings/
        └── route.py              # → /settings
```

Each `route.py` exports [route handlers](#-route-handlers). Each `_middleware.py` defines [directory middleware](#directory-level-middleware).

### Route Conventions

| Convention | Route Example | URL | Handler Parameter |
|------------|---------------|-----|-------------------|
| `users/` | `app/users/route.py` | `/users` | — |
| `[id]/` | `app/users/[id]/route.py` | `/users/123` | `id: str` |
| `[[version]]/` | `app/api/[[version]]/route.py` | `/api` and `/api/v2` | `version: str \| None` |
| `[...path]/` | `app/files/[...path]/route.py` | `/files/a/b/c` | `path: str` |
| `(group)/` | `app/(admin)/settings/route.py` | `/settings` | — |

**Files:** `route.py` contains [handlers](#-route-handlers). `_middleware.py` contains [directory middleware](#directory-level-middleware) that cascades to all subdirectories.

## 📍 Route Handlers

Each `route.py` exports handlers. Supported HTTP methods: `get`, `post`, `put`, `patch`, `delete`, `head`, `options`, `websocket`. Functions prefixed with `_` are private helpers and ignored. Default status codes: `POST` → 201, `DELETE` → 204, all others → 200.

```python
# app/api/users/route.py
from fastapi_filebased_routing import route

# Module-level metadata (applies to all handlers in this file)
TAGS = ["users"]                         # auto-derived from first path segment if omitted
SUMMARY = "User management endpoints"    # OpenAPI summary
DEPRECATED = True                        # mark all handlers as deprecated

# File-level middleware (applies to all handlers in this file, does NOT cascade to subdirectories)
middleware = [rate_limit(100)]

# Simple handler — just a function
async def get():
    """List users."""
    return {"users": []}

# Configured handler — per-handler control over metadata and middleware
class post(route):
    status_code = 200                    # override convention-based 201
    tags = ["admin"]                     # override module-level TAGS
    summary = "Create a user"            # override module-level SUMMARY
    deprecated = True                    # override module-level DEPRECATED
    middleware = [require_role("admin")]  # or use inline: async def middleware(request, call_next): ...

    async def handler(name: str):
        return {"name": name}
```

Both styles coexist freely. Directory bracket names (e.g., `[user_id]`) become path parameters automatically injected into handler signatures. See [`examples/`](examples/) for complete working projects.

## 🔗 Middleware

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

Create a `_middleware.py` file in any directory. Its middleware applies to all routes in that directory and all subdirectories. Use **one** of two forms:

**List form** — multiple middleware functions:

```python
# app/api/_middleware.py — applies to all routes under /api/**
from app.auth import auth_required
from app.logging import request_logger

middleware = [auth_required, request_logger]
```

**Single function form** — one inline middleware:

```python
# app/_middleware.py — root-level timing middleware
import time

async def middleware(request, call_next):
    start = time.monotonic()
    response = await call_next(request)
    response.headers["X-Response-Time"] = f"{time.monotonic() - start:.4f}"
    return response
```

Pick one form per file. If both are defined, standard Python name resolution applies — the last assignment to `middleware` wins.

Directory middleware cascades: a `_middleware.py` in `app/` applies to every route, while one in `app/api/` only applies to routes under `/api/`. Parent middleware always runs before child middleware.

### File-Level Middleware

Set `middleware = [...]` at the top of any `route.py` to apply middleware to all handlers in that file. Unlike directory middleware, file-level middleware does **not** cascade to subdirectories.

```python
# app/api/users/route.py
middleware = [rate_limit(100)]  # applies to get and post below, not to /api/users/[user_id]

async def get():
    """List users. Rate limited."""
    return {"users": []}

async def post(name: str):
    """Create user. Rate limited."""
    return {"name": name}
```

### Handler-Level Middleware

`class handler(route):` blocks support a `middleware` attribute — as a list or a single inline function:

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

## 📦 Examples

See the [`examples/`](examples/) directory for runnable projects:

- **[`basic/`](examples/basic/)** — Routing fundamentals: static, dynamic, CRUD
- **[`middleware/`](examples/middleware/)** — All three middleware layers in action
- **[`advanced/`](examples/advanced/)** — Optional params, catch-all, route groups, WebSockets

## 📖 API Reference

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

## 💡 Why This Plugin?

FastAPI developers building medium-to-large APIs face these problems:

1. **Manual route registration is tedious.** Every endpoint requires updating a centralized router file.
2. **Route discoverability degrades.** Finding the handler for `/api/v1/users/{id}` requires searching across files.
3. **Middleware wiring is repetitive.** Applying auth to 20 admin endpoints means 20 copies of `Depends(require_admin)`.
4. **Full-stack developers experience friction.** Next.js has file-based routing, FastAPI requires manual wiring.

This plugin solves all four with:

- Zero-configuration route discovery from directory structure
- Three-layer middleware system (directory, file, handler) with cascading inheritance
- Next.js feature parity: dynamic params, optional params, catch-all, route groups
- Convention over configuration for status codes, tags, and metadata
- Battle-tested security (path traversal protection, symlink validation)
- WebSocket support, sync and async handlers
- Hot reload compatible (`uvicorn --reload` works out of the box)
- Full mypy strict mode support, coexists with manual FastAPI routing

## 🤝 Contributing

This plugin is extracted from a production codebase and is actively maintained. Issues, feature requests, and pull requests are welcome.

GitHub: https://github.com/rsmdt/fastapi-filebased-routing.py
