"""
WebSocket Event Emitter - Utility for sending real-time updates to frontend.

This module provides a clean interface for services to emit progress events
without tight coupling to Flask-SocketIO implementation details.
"""
from typing import Dict, Any, Optional
from util import logger

# Global reference to SocketIO instance (set by app.py)
_socketio = None


def init_websocket_events(socketio_instance):
    """Initialize the WebSocket event system with SocketIO instance."""
    global _socketio
    _socketio = socketio_instance
    logger.info("WebSocket events initialized")


def emit_event(namespace: str, event_type: str, data: Dict[str, Any], room: Optional[str] = None):
    """
    Emit a WebSocket event to connected clients.

    Args:
        namespace: Event namespace (e.g., 'subscription_enrichment', 'video_discovery')
        event_type: Type of event (e.g., 'channel_ready', 'progress', 'complete')
        data: Event data dictionary
        room: Optional room to emit to (for user-specific events)
    """
    if not _socketio:
        logger.debug(f"WebSocket not initialized, skipping event: {namespace}.{event_type}")
        return

    event_payload = {
        "namespace": namespace,
        "type": event_type,
        "data": data,
        "timestamp": None  # Will be set by frontend
    }

    try:
        _socketio.emit('update', event_payload, room=room)
        logger.debug(f"Emitted WebSocket event: {namespace}.{event_type}")
    except Exception as e:
        logger.error(f"Failed to emit WebSocket event: {e}")


# Convenience functions for common event types
def emit_subscription_event(event_type: str, subscription_data: Dict[str, Any]):
    """Emit subscription enrichment event."""
    emit_event("subscription_enrichment", event_type, subscription_data)


def emit_video_discovery_event(event_type: str, discovery_data: Dict[str, Any]):
    """Emit video discovery event."""
    emit_event("video_discovery", event_type, discovery_data)


def emit_progress_event(namespace: str, current: int, total: int, message: str, extra_data: Dict = None):
    """Emit a progress event with standardized format."""
    data = {
        "current": current,
        "total": total,
        "percent": round((current / total * 100), 1) if total > 0 else 0,
        "message": message
    }

    if extra_data:
        data.update(extra_data)

    emit_event(namespace, "progress", data)