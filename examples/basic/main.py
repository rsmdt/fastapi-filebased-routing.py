"""Basic example demonstrating fastapi-filebased-routing.

This minimal FastAPI application uses create_router_from_path() to
automatically discover and register routes from the app/ directory.

Run with:
    uvicorn main:app --reload

Available endpoints:
    GET  /health          - Health check
    GET  /users           - List all users
    POST /users           - Create a new user
    GET  /users/{user_id} - Get user by ID
    PATCH /users/{user_id} - Update user
    DELETE /users/{user_id} - Delete user
"""

from pathlib import Path

from fastapi import FastAPI
from fastapi_filebased_routing import create_router_from_path

app = FastAPI(title="Basic Example")
app.include_router(create_router_from_path(Path(__file__).parent / "app"))
