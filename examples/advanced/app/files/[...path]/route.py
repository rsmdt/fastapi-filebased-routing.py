"""Catch-all parameter demonstration.

Directory structure: app/files/[...path]/route.py

The [...path] syntax matches ALL remaining path segments:
  - /files/document.txt -> path="document.txt"
  - /files/2024/01/report.pdf -> path="2024/01/report.pdf"
  - /files/images/photos/vacation.jpg -> path="images/photos/vacation.jpg"

Useful for file servers, documentation browsers, or any endpoint
that needs to handle arbitrary path depths.
"""

from pathlib import Path

TAGS = ["files"]


async def get(path: str):
    """Retrieve a file by its full path.

    The catch-all parameter captures all remaining segments.
    """
    # In a real application, you'd validate and serve the actual file
    # This is just a demonstration
    file_path = Path(path)

    return {
        "requested_path": path,
        "filename": file_path.name,
        "parent_directory": str(file_path.parent) if file_path.parent != Path(".") else "/",
        "extension": file_path.suffix,
        "note": "In production, this would serve the actual file content",
    }


def delete(path: str):
    """Delete a file by its full path.

    Demonstrates sync handler with catch-all parameter.
    Returns None for 204 No Content status by convention.
    """
    # In a real application, you'd delete the file
    print(f"Would delete file: {path}")
    return None
