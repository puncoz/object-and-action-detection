"""Event API routes."""

from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from app.api.schemas import (
    EventListResponse,
    EventResponse,
    EventVerify,
    EventNote,
)
from app.services.event_service import event_service
from app.config import settings

router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=EventListResponse)
async def list_events(
    camera_id: Optional[str] = Query(None, description="Filter by camera ID"),
    verified: Optional[bool] = Query(
        None, description="Filter by verification status"),
    from_ts: Optional[datetime] = Query(
        None, alias="from", description="Start timestamp"),
    to_ts: Optional[datetime] = Query(
        None, alias="to", description="End timestamp"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(20, ge=1, le=100, description="Items per page"),
):
    """Get list of events with optional filters."""
    events, total = await event_service.get_events(
        camera_id=camera_id,
        verified=verified,
        from_ts=from_ts,
        to_ts=to_ts,
        page=page,
        page_size=page_size,
    )

    return EventListResponse(
        events=[event_service.event_to_response(e) for e in events],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{event_id}", response_model=EventResponse)
async def get_event(event_id: str):
    """Get a specific event."""
    event = await event_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event_service.event_to_response(event)


@router.post("/{event_id}/verify", response_model=EventResponse)
async def verify_event(event_id: str, body: EventVerify):
    """Mark an event as verified or rejected."""
    event = await event_service.verify_event(event_id, body.verified)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event_service.event_to_response(event)


@router.post("/{event_id}/note", response_model=EventResponse)
async def add_note(event_id: str, body: EventNote):
    """Add a note to an event."""
    event = await event_service.add_note(event_id, body.note)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return event_service.event_to_response(event)


@router.get("/{event_id}/snapshot")
async def get_event_snapshot(event_id: str):
    """Get the snapshot image for an event."""
    event = await event_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.snapshot_path:
        raise HTTPException(status_code=404, detail="No snapshot available")

    snapshot_path = Path(event.snapshot_path)
    if not snapshot_path.exists():
        raise HTTPException(status_code=404, detail="Snapshot file not found")

    return FileResponse(
        snapshot_path,
        media_type="image/jpeg",
        filename=f"event_{event_id}_snapshot.jpg",
    )


@router.get("/{event_id}/clip")
async def get_event_clip(event_id: str):
    """Get the video clip for an event."""
    event = await event_service.get_event(event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.clip_path:
        raise HTTPException(status_code=404, detail="No clip available")

    clip_path = Path(event.clip_path)
    if not clip_path.exists():
        raise HTTPException(status_code=404, detail="Clip file not found")

    return FileResponse(
        clip_path,
        media_type="video/mp4",
        filename=f"event_{event_id}_clip.mp4",
    )


@router.delete("/{event_id}", status_code=204)
async def delete_event(event_id: str):
    """Delete an event."""
    success = await event_service.delete_event(event_id)
    if not success:
        raise HTTPException(status_code=404, detail="Event not found")
