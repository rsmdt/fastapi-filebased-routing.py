"""Core routing components — framework-agnostic."""

from fastapi_filebased_routing.core.middleware import RouteConfig, route

__all__ = ["route", "RouteConfig"]
