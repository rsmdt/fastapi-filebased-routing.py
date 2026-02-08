"""Server-Sent Events (SSE) demonstration.

Directory structure: app/events/route.py

Demonstrates streaming responses for real-time updates.
SSE is useful for:
- Live updates (dashboards, notifications)
- Progress tracking
- Real-time feeds
- One-way server-to-client communication
"""

import asyncio
from datetime import datetime

from fastapi.responses import StreamingResponse

TAGS = ["events", "streaming"]


async def _event_generator():
    """Generate server-sent events.

    Yields events in SSE format:
    data: <json>\n\n
    """
    count = 0
    while count < 10:  # Limit to 10 events for demo
        count += 1

        # SSE format requires 'data: ' prefix and double newline
        event_data = {
            "event_number": count,
            "timestamp": datetime.now().isoformat(),
            "message": f"Event {count} of 10",
        }

        # Format as SSE event
        yield f"data: {event_data}\n\n"

        # Wait 1 second between events
        await asyncio.sleep(1)

    # Send final event
    yield "data: {\"event_number\": 11, \"message\": \"Stream complete\"}\n\n"


async def get():
    """Stream server-sent events.

    Returns a StreamingResponse with text/event-stream content type.

    Connect via:
      curl http://localhost:8000/events
      or in browser with EventSource API
    """
    return StreamingResponse(
        _event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
