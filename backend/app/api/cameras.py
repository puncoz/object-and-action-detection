"""Camera API routes."""

import asyncio
from typing import Optional

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse

from app.api.schemas import (
    CameraCreate,
    CameraResponse,
    CameraListResponse,
    CameraStatus,
    CameraType,
)
from app.services.camera_manager import camera_manager

router = APIRouter(prefix="/api/cameras", tags=["cameras"])


@router.get("", response_model=CameraListResponse)
async def list_cameras():
    """Get all cameras."""
    cameras = await camera_manager.get_cameras()

    # Update status from processors
    camera_responses = []
    for cam in cameras:
        processor = camera_manager.get_processor(cam.id)
        status = processor.status if processor else cam.status

        camera_responses.append(
            CameraResponse(
                id=cam.id,
                name=cam.name,
                source=cam.source,
                type=CameraType(cam.type),
                status=CameraStatus(status),
                created_at=cam.created_at,
            )
        )

    return CameraListResponse(cameras=camera_responses, total=len(camera_responses))


@router.post("", response_model=CameraResponse, status_code=201)
async def create_camera(camera: CameraCreate):
    """Add a new camera."""
    cam = await camera_manager.add_camera(camera)
    return CameraResponse(
        id=cam.id,
        name=cam.name,
        source=cam.source,
        type=CameraType(cam.type),
        status=CameraStatus(cam.status),
        created_at=cam.created_at,
    )


@router.get("/{camera_id}", response_model=CameraResponse)
async def get_camera(camera_id: str):
    """Get a specific camera."""
    cam = await camera_manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    processor = camera_manager.get_processor(camera_id)
    status = processor.status if processor else cam.status

    return CameraResponse(
        id=cam.id,
        name=cam.name,
        source=cam.source,
        type=CameraType(cam.type),
        status=CameraStatus(status),
        created_at=cam.created_at,
    )


@router.delete("/{camera_id}", status_code=204)
async def delete_camera(camera_id: str):
    """Delete a camera."""
    success = await camera_manager.delete_camera(camera_id)
    if not success:
        raise HTTPException(status_code=404, detail="Camera not found")
    return Response(status_code=204)


@router.post("/{camera_id}/start")
async def start_camera(camera_id: str):
    """Start processing for a camera."""
    cam = await camera_manager.get_camera(camera_id)
    if not cam:
        raise HTTPException(status_code=404, detail="Camera not found")

    success = await camera_manager.start_camera(camera_id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to start camera")

    return {"status": "started", "camera_id": camera_id}


@router.post("/{camera_id}/stop")
async def stop_camera(camera_id: str):
    """Stop processing for a camera."""
    await camera_manager.stop_camera(camera_id)
    return {"status": "stopped", "camera_id": camera_id}


@router.get("/{camera_id}/mjpeg")
async def mjpeg_stream(camera_id: str):
    """Get MJPEG video stream for a camera."""
    processor = camera_manager.get_processor(camera_id)
    if not processor:
        raise HTTPException(
            status_code=404,
            detail="Camera not running. Start the camera first.",
        )

    async def generate():
        """Generate MJPEG frames pushed as soon as each new frame is ready."""
        frame_event = processor.frame_event
        while processor.is_running:
            # Wait for the frame loop to signal a new frame (timeout avoids
            # hanging forever if the camera stops between checks)
            try:
                await asyncio.wait_for(frame_event.wait(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            frame_event.clear()

            frame_bytes = processor.get_mjpeg_frame()
            if frame_bytes:
                yield (
                    b"--frame\r\n"
                    b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n"
                )

    return StreamingResponse(
        generate(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@router.get("/{camera_id}/snapshot")
async def get_snapshot(camera_id: str):
    """Get current frame snapshot."""
    processor = camera_manager.get_processor(camera_id)
    if not processor:
        raise HTTPException(
            status_code=404,
            detail="Camera not running",
        )

    frame_bytes = processor.get_mjpeg_frame()
    if not frame_bytes:
        raise HTTPException(status_code=503, detail="No frame available")

    return Response(content=frame_bytes, media_type="image/jpeg")


@router.get("/{camera_id}/status")
async def get_camera_status(camera_id: str):
    """Get detailed camera status."""
    processor = camera_manager.get_processor(camera_id)
    if not processor:
        cam = await camera_manager.get_camera(camera_id)
        if not cam:
            raise HTTPException(status_code=404, detail="Camera not found")
        return {
            "camera_id": camera_id,
            "status": cam.status,
            "fps": 0,
            "frame_count": 0,
            "running": False,
        }

    return {
        "camera_id": camera_id,
        "status": processor.status,
        "fps": processor.fps,
        "frame_count": processor.frame_count,
        "running": processor.is_running,
    }
