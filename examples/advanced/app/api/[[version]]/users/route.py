"""Optional parameter demonstration.

Directory structure: app/api/[[version]]/users/route.py

The [[version]] syntax creates TWO routes:
  1. /api/users (version parameter excluded)
  2. /api/{version}/users (version parameter included)

This allows clients to optionally specify a version in the URL.
"""

TAGS = ["users"]


def get(version: str | None = None):
    """List users with optional API versioning.

    Demonstrates optional parameter pattern where the same handler
    serves both versioned and non-versioned endpoints.
    """
    if version:
        return {
            "users": ["alice", "bob", "charlie"],
            "api_version": version,
            "note": f"Using API version {version}",
        }
    return {
        "users": ["alice", "bob", "charlie"],
        "api_version": "default",
        "note": "Using default API version",
    }


async def post(user_data: dict, version: str | None = None):
    """Create a new user with optional API versioning.

    Demonstrates async handler with optional parameter.
    """
    return {
        "message": "User created",
        "user": user_data,
        "api_version": version or "default",
    }
