"""Tests for dispatch() class-based middleware adapter."""

import asyncio
from typing import Any
from unittest.mock import AsyncMock

import pytest

from fastapi_filebased_routing.core.middleware import _noop_app, dispatch


class _FakeMiddleware:
    """Fake middleware class for testing dispatch()."""

    instances: list["_FakeMiddleware"] = []

    def __init__(self, app: Any, **kwargs: Any) -> None:
        self.app = app
        self.kwargs = kwargs
        _FakeMiddleware.instances.append(self)

    async def dispatch(self, request: Any, call_next: Any) -> Any:
        response = await call_next(request)
        return response

    @classmethod
    def reset(cls) -> None:
        cls.instances.clear()


class _NoDispatchMiddleware:
    """Middleware class without a dispatch method."""

    def __init__(self, app: Any) -> None:
        self.app = app


@pytest.fixture(autouse=True)
def _reset_fake() -> None:
    """Reset fake middleware state before each test."""
    _FakeMiddleware.reset()


class TestDispatch:
    """Unit tests for the dispatch() adapter."""

    def test_dispatch_returns_async_callable(self) -> None:
        """dispatch() should return an async callable."""
        mw = dispatch(_FakeMiddleware)

        assert callable(mw)
        assert asyncio.iscoroutinefunction(mw)

    def test_dispatch_lazy_instantiation(self) -> None:
        """Class should NOT be instantiated at dispatch() call time."""
        dispatch(_FakeMiddleware)

        assert len(_FakeMiddleware.instances) == 0

    @pytest.mark.anyio()
    async def test_dispatch_passes_kwargs(self) -> None:
        """Keyword arguments should be forwarded to the class constructor."""
        mw = dispatch(_FakeMiddleware, limit=40, burst=10)

        call_next = AsyncMock(return_value="response")
        await mw("request", call_next)

        instance = _FakeMiddleware.instances[0]
        assert instance.kwargs == {"limit": 40, "burst": 10}

    @pytest.mark.anyio()
    async def test_dispatch_no_kwargs(self) -> None:
        """dispatch() should work with a class that only takes app."""
        mw = dispatch(_FakeMiddleware)

        call_next = AsyncMock(return_value="response")
        await mw("request", call_next)

        instance = _FakeMiddleware.instances[0]
        assert instance.kwargs == {}

    @pytest.mark.anyio()
    async def test_dispatch_reuses_instance(self) -> None:
        """Second call should reuse the same instance, not create a new one."""
        mw = dispatch(_FakeMiddleware)
        call_next = AsyncMock(return_value="response")

        await mw("request1", call_next)
        await mw("request2", call_next)

        assert len(_FakeMiddleware.instances) == 1

    def test_dispatch_name_set(self) -> None:
        """__name__ should be set to dispatch(ClassName)."""
        mw = dispatch(_FakeMiddleware)

        assert mw.__name__ == "dispatch(_FakeMiddleware)"
        assert mw.__qualname__ == "dispatch(_FakeMiddleware)"

    @pytest.mark.anyio()
    async def test_dispatch_delegates_to_dispatch_method(self) -> None:
        """dispatch() should call instance.dispatch with correct args."""
        call_next = AsyncMock(return_value="response")
        mw = dispatch(_FakeMiddleware)

        result = await mw("the_request", call_next)

        assert result == "response"
        call_next.assert_called_once_with("the_request")

    @pytest.mark.anyio()
    async def test_dispatch_missing_dispatch_method(self) -> None:
        """Missing dispatch method should raise AttributeError on first call, not at setup."""
        mw = dispatch(_NoDispatchMiddleware)

        # Setup succeeds — error is deferred
        assert callable(mw)

        # First call triggers instantiation + AttributeError
        with pytest.raises(AttributeError):
            await mw("request", AsyncMock())

    @pytest.mark.anyio()
    async def test_dispatch_noop_app_passed(self) -> None:
        """Class should receive _noop_app as the app argument."""
        mw = dispatch(_FakeMiddleware)

        call_next = AsyncMock(return_value="response")
        await mw("request", call_next)

        instance = _FakeMiddleware.instances[0]
        assert instance.app is _noop_app
