"""Camera manager service for handling multiple video sources."""

import asyncio
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.schemas import CameraCreate, CameraResponse, CameraStatus, DetectionFrame
from app.core.frame_processor import FrameProcessor
from app.database import Camera, async_session


class CameraManager:
    """
    Manages multiple camera sources and their processing pipelines.

    Singleton-like service that tracks all active cameras.
    """

    def __init__(self):
        self._processors: Dict[str, FrameProcessor] = {}
        self._ws_callbacks: Dict[str,
                                 List[Callable[[DetectionFrame], None]]] = {}
        self._event_callback: Optional[Callable[[Dict[str, Any]], None]] = None

    def set_event_callback(self, callback: Callable[[Dict[str, Any]], None]):
        """Set callback for completed events."""
        self._event_callback = callback

    def add_ws_callback(self, camera_id: str, callback: Callable[[DetectionFrame], None]):
        """Add a WebSocket callback for a camera."""
        if camera_id not in self._ws_callbacks:
            self._ws_callbacks[camera_id] = []
        self._ws_callbacks[camera_id].append(callback)

    def remove_ws_callback(self, camera_id: str, callback: Callable[[DetectionFrame], None]):
        """Remove a WebSocket callback."""
        if camera_id in self._ws_callbacks:
            try:
                self._ws_callbacks[camera_id].remove(callback)
            except ValueError:
                pass

    def _broadcast_detection(self, camera_id: str, detection: DetectionFrame):
        """Broadcast detection to all WebSocket callbacks."""
        if camera_id in self._ws_callbacks:
            for callback in self._ws_callbacks[camera_id]:
                try:
                    callback(detection)
                except Exception as e:
                    print(f"WS callback error: {e}")

    async def add_camera(self, camera_data: CameraCreate) -> Camera:
        """Add a new camera to the database."""
        async with async_session() as session:
            camera = Camera(
                id=str(uuid4()),
                name=camera_data.name,
                source=camera_data.source,
                type=camera_data.type.value,
                status="stopped",
            )
            session.add(camera)
            await session.commit()
            await session.refresh(camera)
            return camera

    async def get_cameras(self) -> List[Camera]:
        """Get all cameras from the database."""
        async with async_session() as session:
            result = await session.execute(select(Camera))
            return list(result.scalars().all())

    async def get_camera(self, camera_id: str) -> Optional[Camera]:
        """Get a specific camera."""
        async with async_session() as session:
            result = await session.execute(
                select(Camera).where(Camera.id == camera_id)
            )
            return result.scalar_one_or_none()

    async def delete_camera(self, camera_id: str) -> bool:
        """Delete a camera."""
        # Stop if running
        await self.stop_camera(camera_id)

        async with async_session() as session:
            result = await session.execute(
                select(Camera).where(Camera.id == camera_id)
            )
            camera = result.scalar_one_or_none()
            if camera:
                await session.delete(camera)
                await session.commit()
                return True
        return False

    async def start_camera(self, camera_id: str) -> bool:
        """Start processing for a camera."""
        if camera_id in self._processors:
            return True  # Already running

        camera = await self.get_camera(camera_id)
        if not camera:
            return False

        # Create processor
        processor = FrameProcessor(
            camera_id=camera_id,
            source=camera.source,
            source_type=camera.type,
            on_event_completed=self._event_callback,
            on_frame_processed=lambda d: self._broadcast_detection(
                camera_id, d),
        )

        # Start processing
        success = await processor.start()
        if success:
            self._processors[camera_id] = processor
            # Update status in database
            await self._update_camera_status(camera_id, "running")
        else:
            await self._update_camera_status(camera_id, "error")

        return success

    async def stop_camera(self, camera_id: str) -> bool:
        """Stop processing for a camera."""
        if camera_id not in self._processors:
            return True  # Not running

        processor = self._processors[camera_id]
        await processor.stop()
        del self._processors[camera_id]

        # Update status in database
        await self._update_camera_status(camera_id, "stopped")

        return True

    async def _update_camera_status(self, camera_id: str, status: str):
        """Update camera status in database."""
        async with async_session() as session:
            result = await session.execute(
                select(Camera).where(Camera.id == camera_id)
            )
            camera = result.scalar_one_or_none()
            if camera:
                camera.status = status
                await session.commit()

    def get_processor(self, camera_id: str) -> Optional[FrameProcessor]:
        """Get the processor for a camera."""
        return self._processors.get(camera_id)

    def get_running_cameras(self) -> List[str]:
        """Get list of running camera IDs."""
        return list(self._processors.keys())

    async def stop_all(self):
        """Stop all camera processors."""
        for camera_id in list(self._processors.keys()):
            await self.stop_camera(camera_id)


# Global singleton instance
camera_manager = CameraManager()
