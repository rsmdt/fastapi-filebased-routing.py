"""User collection endpoints."""

from fastapi import HTTPException

TAGS = ["users"]

# In-memory storage for demonstration purposes
_users_db: dict[str, dict[str, str]] = {}
_next_id = 1


async def get() -> dict:
    """List all users."""
    users = list(_users_db.values())
    return {
        "users": users,
        "count": len(users),
    }


async def post(name: str, email: str) -> dict:
    """Create a new user."""
    global _next_id

    for existing_user in _users_db.values():
        if existing_user["email"] == email:
            raise HTTPException(
                status_code=400,
                detail=f"Email {email} is already registered",
            )

    user_id = str(_next_id)
    _next_id += 1

    new_user = {
        "id": user_id,
        "name": name,
        "email": email,
    }

    _users_db[user_id] = new_user
    return new_user
