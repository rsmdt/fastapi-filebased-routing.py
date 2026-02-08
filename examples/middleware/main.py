"""Middleware example for fastapi-filebased-routing.

Run with: uvicorn main:app --reload
"""
from fastapi import FastAPI
from fastapi_filebased_routing import create_router_from_path

app = FastAPI(title="Middleware Example")
app.include_router(create_router_from_path("app"))
