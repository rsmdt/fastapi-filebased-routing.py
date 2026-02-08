"""Tests for middleware chain building functions and normalize_middleware."""

from types import SimpleNamespace
from typing import Any

import pytest

from fastapi_filebased_routing.core.middleware import (
    _wrap_with_middleware,
    build_middleware_chain,
    normalize_middleware,
)
from fastapi_filebased_routing.exceptions import RouteValidationError

# === normalize_middleware tests ===


class TestNormalizeMiddleware:
    """Tests for the normalize_middleware utility function."""

    def test_none_returns_empty_tuple(self) -> None:
        """None middleware returns empty tuple."""
        result = normalize_middleware(None, source="test")
        assert result == ()
        assert isinstance(result, tuple)

    def test_single_callable_returns_tuple_of_one(self) -> None:
        """Single callable is wrapped in a tuple."""

        async def mw(request: Any, call_next: Any) -> Any:
            return await call_next(request)

        result = normalize_middleware(mw, source="test")
        assert result == (mw,)
        assert isinstance(result, tuple)

    def test_list_of_callables_returns_tuple(self) -> None:
        """List of callables is converted to a tuple."""

        async def mw1(request: Any, call_next: Any) -> Any:
            return await call_next(request)

        async def mw2(request: Any, call_next: Any) -> Any:
            return await call_next(request)

        result = normalize_middleware([mw1, mw2], source="test")
        assert result == (mw1, mw2)
        assert isinstance(result, tuple)

    def test_tuple_of_callables_preserved(self) -> None:
        """Tuple of callables is preserved as-is (already a tuple)."""

        async def mw(request: Any, call_next: Any) -> Any:
            return await call_next(request)

        result = normalize_middleware((mw,), source="test")
        assert result == (mw,)
        assert isinstance(result, tuple)

    def test_empty_list_returns_empty_tuple(self) -> None:
        """Empty list returns empty tuple."""
        result = normalize_middleware([], source="test")
        assert result == ()
        assert isinstance(result, tuple)

    def test_empty_tuple_returns_empty_tuple(self) -> None:
        """Empty tuple returns empty tuple."""
        result = normalize_middleware((), source="test")
        assert result == ()
        assert isinstance(result, tuple)

    def test_invalid_type_raises_validation_error(self) -> None:
        """Non-callable, non-list, non-tuple raises RouteValidationError."""
        with pytest.raises(RouteValidationError, match="middleware must be a list or callable"):
            normalize_middleware("invalid", source="test handler")

    def test_invalid_type_includes_source_in_error(self) -> None:
        """Error message includes the source context."""
        with pytest.raises(RouteValidationError, match="test handler"):
            normalize_middleware(42, source="test handler")

    def test_default_source_is_empty_string(self) -> None:
        """Source parameter defaults to empty string."""
        # Should work without source
        result = normalize_middleware(None)
        assert result == ()

    def test_int_raises_validation_error(self) -> None:
        """Integer value raises RouteValidationError."""
        with pytest.raises(RouteValidationError, match="got int"):
            normalize_middleware(123, source="test")


@pytest.mark.asyncio
async def test_build_middleware_chain_empty_stack_returns_handler_unchanged() -> None:
    """Empty middleware stack should return handler unchanged."""

    async def handler(request: Any) -> str:
        return "handler_response"

    wrapped = build_middleware_chain(handler, [])

    assert wrapped is handler


@pytest.mark.asyncio
async def test_build_middleware_chain_single_middleware() -> None:
    """Single middleware should wrap handler correctly."""

    async def handler(request: Any) -> str:
        return f"handler:{request.data}"

    async def middleware(request: Any, call_next: Any) -> str:
        request.data = f"mw[{request.data}]"
        response = await call_next(request)
        return f"mw-after:{response}"

    request = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(handler, [middleware])

    result = await wrapped(request)
    assert result == "mw-after:handler:mw[test]"


@pytest.mark.asyncio
async def test_build_middleware_chain_multiple_middleware_execution_order() -> None:
    """Multiple middleware should execute in order: first in list is outermost."""
    execution_order: list[str] = []

    async def handler(request: Any) -> str:
        execution_order.append("handler")
        return f"handler:{request.data}"

    async def mw1(request: Any, call_next: Any) -> str:
        execution_order.append("mw1_before")
        response = await call_next(request)
        execution_order.append("mw1_after")
        return f"mw1[{response}]"

    async def mw2(request: Any, call_next: Any) -> str:
        execution_order.append("mw2_before")
        response = await call_next(request)
        execution_order.append("mw2_after")
        return f"mw2[{response}]"

    request = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(handler, [mw1, mw2])

    result = await wrapped(request)

    # First in list (mw1) executes first (outermost)
    assert execution_order == ["mw1_before", "mw2_before", "handler", "mw2_after", "mw1_after"]
    assert result == "mw1[mw2[handler:test]]"


@pytest.mark.asyncio
async def test_middleware_can_modify_response() -> None:
    """Middleware can modify response after call_next."""

    async def handler(request: Any) -> dict[str, Any]:
        return {"status": "ok", "data": request.data}

    async def add_timestamp(request: Any, call_next: Any) -> dict[str, Any]:
        response = await call_next(request)
        response["timestamp"] = "2024-01-01"
        return response

    request = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(handler, [add_timestamp])

    result = await wrapped(request)
    assert result == {"status": "ok", "data": "test", "timestamp": "2024-01-01"}


@pytest.mark.asyncio
async def test_middleware_can_short_circuit() -> None:
    """Middleware can return without calling call_next."""

    async def handler(request: Any) -> str:
        return "handler_response"

    async def auth_middleware(request: Any, call_next: Any) -> str:
        if not hasattr(request, "token"):
            return "unauthorized"
        return await call_next(request)

    # Request without token
    request_no_token = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(handler, [auth_middleware])

    result = await wrapped(request_no_token)
    assert result == "unauthorized"

    # Request with token
    request_with_token = SimpleNamespace(data="test", token="valid")
    result = await wrapped(request_with_token)
    assert result == "handler_response"


@pytest.mark.asyncio
async def test_wrapped_function_preserves_debug_name() -> None:
    """Wrapped function should have debug-friendly __name__."""

    async def my_handler(request: Any) -> str:
        return "ok"

    async def logging_middleware(request: Any, call_next: Any) -> str:
        return await call_next(request)

    wrapped = build_middleware_chain(my_handler, [logging_middleware])

    assert "logging_middleware" in wrapped.__name__
    assert "my_handler" in wrapped.__name__


@pytest.mark.asyncio
async def test_exception_in_middleware_propagates() -> None:
    """Exception in middleware should propagate correctly."""

    async def handler(request: Any) -> str:
        return "ok"

    async def failing_middleware(request: Any, call_next: Any) -> str:
        raise ValueError("middleware error")

    request = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(handler, [failing_middleware])

    with pytest.raises(ValueError, match="middleware error"):
        await wrapped(request)


@pytest.mark.asyncio
async def test_exception_in_handler_propagates_through_middleware() -> None:
    """Exception in handler should propagate through middleware stack."""

    async def handler(request: Any) -> str:
        raise RuntimeError("handler error")

    async def mw1(request: Any, call_next: Any) -> str:
        return await call_next(request)

    async def mw2(request: Any, call_next: Any) -> str:
        return await call_next(request)

    request = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(handler, [mw1, mw2])

    with pytest.raises(RuntimeError, match="handler error"):
        await wrapped(request)


@pytest.mark.asyncio
async def test_context_enrichment_via_request_state() -> None:
    """Middleware can enrich request.state and handler reads it."""

    async def handler(request: Any) -> dict[str, Any]:
        return {
            "user_id": request.state.user_id,
            "role": request.state.role,
        }

    async def auth_middleware(request: Any, call_next: Any) -> Any:
        request.state = SimpleNamespace(user_id=123, role="admin")
        return await call_next(request)

    request = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(handler, [auth_middleware])

    result = await wrapped(request)
    assert result == {"user_id": 123, "role": "admin"}


@pytest.mark.asyncio
async def test_multiple_middleware_can_enrich_request_state() -> None:
    """Multiple middleware can add to request.state."""

    async def handler(request: Any) -> dict[str, Any]:
        return {
            "user_id": request.state.user_id,
            "request_id": request.state.request_id,
            "tenant": request.state.tenant,
        }

    async def auth_middleware(request: Any, call_next: Any) -> Any:
        if not hasattr(request, "state"):
            request.state = SimpleNamespace()
        request.state.user_id = 123
        return await call_next(request)

    async def request_id_middleware(request: Any, call_next: Any) -> Any:
        if not hasattr(request, "state"):
            request.state = SimpleNamespace()
        request.state.request_id = "req-456"
        return await call_next(request)

    async def tenant_middleware(request: Any, call_next: Any) -> Any:
        if not hasattr(request, "state"):
            request.state = SimpleNamespace()
        request.state.tenant = "org-789"
        return await call_next(request)

    request = SimpleNamespace(data="test")
    wrapped = build_middleware_chain(
        handler, [auth_middleware, request_id_middleware, tenant_middleware]
    )

    result = await wrapped(request)
    assert result == {
        "user_id": 123,
        "request_id": "req-456",
        "tenant": "org-789",
    }


@pytest.mark.asyncio
async def test_wrap_with_middleware_creates_call_next_with_correct_semantics() -> None:
    """_wrap_with_middleware should create call_next that invokes next_handler."""
    call_next_invoked = False

    async def handler(request: Any) -> str:
        return f"handler:{request.data}"

    async def middleware(request: Any, call_next: Any) -> str:
        nonlocal call_next_invoked
        result = await call_next(request)
        call_next_invoked = True
        return f"mw:{result}"

    request = SimpleNamespace(data="test")
    wrapped = _wrap_with_middleware(handler, middleware)

    result = await wrapped(request)
    assert call_next_invoked
    assert result == "mw:handler:test"
