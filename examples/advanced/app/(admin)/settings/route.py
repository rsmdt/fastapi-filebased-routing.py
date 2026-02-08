"""Route group demonstration.

Directory structure: app/(admin)/settings/route.py

The (admin) parentheses syntax creates a ROUTE GROUP:
  - The directory is used for code organization only
  - It does NOT appear in the URL path
  - Result: /settings (NOT /admin/settings)

Use route groups to organize related endpoints without affecting URLs.
"""

TAGS = ["admin", "settings"]


async def get():
    """Get application settings.

    Note: This route is at /settings, not /admin/settings.
    The (admin) folder is purely for organization.
    """
    return {
        "settings": {
            "app_name": "Advanced Routing Demo",
            "max_upload_size": "10MB",
            "debug_mode": False,
        },
        "note": "Route groups organize code without affecting URLs",
    }


async def put(new_settings: dict):
    """Update application settings.

    Demonstrates multiple HTTP methods in a route group.
    """
    return {
        "message": "Settings updated",
        "updated_settings": new_settings,
    }
