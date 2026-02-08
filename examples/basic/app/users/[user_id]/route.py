"""Individual user endpoints."""

from fastapi import HTTPException

TAGS = ["users"]

# Shared storage — in a real app this would be a database
_users_db: dict[str, dict[str, str]] = {}


def get(user_id: str) -> dict:
    """Get a user by ID."""
    user = _users_db.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    return user


async def patch(user_id: str, name: str | None = None, email: str | None = None) -> dict:
    """Update a user's information."""
    user = _users_db.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    if name is not None:
        user["name"] = name
    if email is not None:
        user["email"] = email

    return user


async def delete(user_id: str) -> None:
    """Delete a user."""
    user = _users_db.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")

    del _users_db[user_id]
