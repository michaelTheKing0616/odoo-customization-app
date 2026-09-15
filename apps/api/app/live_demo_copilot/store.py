"""Compatibility shim — durable sessions live in service.py; SSE in events.py."""

from app.live_demo_copilot.events import EVENT_BUS

# Legacy name used by older imports
STORE = EVENT_BUS
