"""WebSocket handler for real-time detection streaming."""

import asyncio
import json
from typing import Dict, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.schemas import DetectionFrame
from app.services.camera_manager import camera_manager

router = APIRouter(tags=["websocket"])


class ConnectionManager:
    """Manages WebSocket connections for each camera."""

    def __init__(self):
        self.active_connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, camera_id: str):
        """Accept a new WebSocket connection."""
        await websocket.accept()
        if camera_id not in self.active_connections:
            self.active_connections[camera_id] = set()
        self.active_connections[camera_id].add(websocket)

    def disconnect(self, websocket: WebSocket, camera_id: str):
        """Remove a WebSocket connection."""
        if camera_id in self.active_connections:
            self.active_connections[camera_id].discard(websocket)
            if not self.active_connections[camera_id]:
                del self.active_connections[camera_id]

    async def broadcast(self, camera_id: str, message: str):
        """Broadcast a message to all connections for a camera."""
        if camera_id not in self.active_connections:
            return

        disconnected = set()
        for connection in self.active_connections[camera_id]:
            try:
                await connection.send_text(message)
            except Exception:
                disconnected.add(connection)

        # Clean up disconnected
        for conn in disconnected:
            self.active_connections[camera_id].discard(conn)

    def get_connection_count(self, camera_id: str) -> int:
        """Get number of active connections for a camera."""
        return len(self.active_connections.get(camera_id, set()))


# Global connection manager
ws_manager = ConnectionManager()


@router.websocket("/ws/cameras/{camera_id}")
async def camera_websocket(websocket: WebSocket, camera_id: str):
    """
    WebSocket endpoint for real-time detection data.

    Clients connect here to receive detection updates for a specific camera.
    """
    await ws_manager.connect(websocket, camera_id)

    # Register callback for detection updates
    def on_detection(detection: DetectionFrame):
        """Callback when a detection is processed."""
        try:
            message = detection.model_dump_json()
            asyncio.create_task(ws_manager.broadcast(camera_id, message))
        except Exception as e:
            print(f"Detection broadcast error: {e}")

    camera_manager.add_ws_callback(camera_id, on_detection)

    try:
        # Keep connection alive and handle incoming messages
        while True:
            try:
                # Wait for any incoming message (ping/pong or commands)
                data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=30.0,
                )

                # Handle incoming commands
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong"})
                    elif msg_type == "subscribe":
                        # Already subscribed by connecting
                        await websocket.send_json({
                            "type": "subscribed",
                            "camera_id": camera_id,
                        })
                except json.JSONDecodeError:
                    pass

            except asyncio.TimeoutError:
                # Send keepalive
                try:
                    await websocket.send_json({"type": "keepalive"})
                except Exception:
                    break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        camera_manager.remove_ws_callback(camera_id, on_detection)
        ws_manager.disconnect(websocket, camera_id)


@router.websocket("/ws/events")
async def events_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for real-time event notifications.

    Clients connect here to receive notifications when new events are created.
    """
    await websocket.accept()

    # This will be connected to event_service via callback
    event_queue: asyncio.Queue = asyncio.Queue()

    async def on_event(event_data: dict):
        """Callback when an event is created."""
        await event_queue.put(event_data)

    # Register for event notifications
    # Note: In production, this would be connected to event_service

    try:
        while True:
            try:
                # Check for new events
                event = await asyncio.wait_for(event_queue.get(), timeout=30.0)
                await websocket.send_json({
                    "type": "event",
                    "data": event,
                })
            except asyncio.TimeoutError:
                # Send keepalive
                await websocket.send_json({"type": "keepalive"})
            except Exception:
                break

    except WebSocketDisconnect:
        pass
    except Exception as e:
        print(f"Events WebSocket error: {e}")
