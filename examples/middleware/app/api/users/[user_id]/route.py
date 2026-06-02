"""User detail with handler-level middleware."""

from fastapi_filebased_routing import Route


async def get(user_id: str) -> dict:
    """Get user details."""
    return {"user_id": user_id}


class DELETE(Route):
    """Delete user - requires admin role."""

    tags = ["admin"]
    status_code = 200

    @staticmethod
    async def handler(user_id: str) -> dict:
        return {"deleted": user_id}
