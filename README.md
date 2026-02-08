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

Override by returning a FastAPI `Response` with a custom status code.

## Complete Example

```
app/
├── health/
│   └── route.py
├── users/
│   ├── route.py
│   └── [user_id]/
│       └── route.py
└── ws/
    └── chat/
        └── route.py
```

```python
# app/health/route.py
async def get():
    """Health check endpoint."""
    return {"status": "ok"}
```

```python
# app/users/route.py
from typing import List
from pydantic import BaseModel

class User(BaseModel):
    id: str
    name: str

TAGS = ["users"]

async def get() -> List[User]:
    """List all users."""
    return [{"id": "1", "name": "Alice"}]

async def post(name: str) -> User:
    """Create a new user."""
    return {"id": "2", "name": name}
```

```python
# app/users/[user_id]/route.py
TAGS = ["users"]

async def get(user_id: str):
    """Get user by ID."""
    return {"user_id": user_id, "name": "Alice"}

async def delete(user_id: str):
    """Delete user by ID."""
    return None  # Returns 204 No Content
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

## Features

- Zero-configuration route discovery
- Next.js feature parity (dynamic params, optional params, catch-all, route groups)
- Battle-tested security (path traversal protection, symlink validation)
- Convention over configuration (status codes, tags, metadata)
- WebSocket support
- Sync and async handlers
- Works with FastAPI's existing routing (coexists with manual routes)
- Hot reload compatible (uvicorn --reload works out of the box)
- Type-safe with full mypy strict mode support

## Why This Plugin?

FastAPI developers building medium-to-large APIs face three problems:

1. **Manual route registration is tedious.** Every endpoint requires updating a centralized router file.
2. **Route discoverability degrades.** Finding the handler for `/api/v1/users/{id}` requires searching across files.
3. **Full-stack developers experience friction.** Next.js has file-based routing, FastAPI requires manual wiring.

This plugin solves all three by bringing the Next.js routing convention to FastAPI.

### Comparison with Alternatives

| Feature | fastapi-filebased-routing | fastapi-file-router | runapi |
|---------|--------------------------|---------------------|--------|
| Dynamic params `[id]` | ✅ | ✅ | ✅ |
| Optional params `[[version]]` | ✅ | ❌ | ❌ |
| Catch-all `[...path]` | ✅ | ❌ | ❌ |
| Route groups `(name)` | ✅ | ❌ | ❌ |
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
