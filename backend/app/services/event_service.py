"""Event service for managing hydration detection events."""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from sqlalchemy import select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import Event, async_session
from app.api.schemas import EventResponse


class EventService:
    """Service for managing hydration detection events."""

    async def create_event(self, event_data: Dict[str, Any]) -> Event:
        """Create a new event from detection data."""
        async with async_session() as session:
            event = Event(
                id=event_data.get("id", str(uuid4())),
                camera_id=event_data["camera_id"],
                track_id=event_data.get("track_id", 0),
                start_ts=event_data["start_ts"],
                end_ts=event_data.get("end_ts"),
                sequence=json.dumps(event_data.get("sequence", [])),
                confidence=event_data.get("confidence", 0.0),
                snapshot_path=event_data.get("snapshot_path"),
                clip_path=event_data.get("clip_path"),
                verified=None,
                note=None,
            )
            session.add(event)
            await session.commit()
            await session.refresh(event)
            return event

    async def get_events(
        self,
        camera_id: Optional[str] = None,
        verified: Optional[bool] = None,
        from_ts: Optional[datetime] = None,
        to_ts: Optional[datetime] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[List[Event], int]:
        """Get events with optional filters."""
        async with async_session() as session:
            # Build query
            query = select(Event)
            count_query = select(Event)

            conditions = []
            if camera_id:
                conditions.append(Event.camera_id == camera_id)
            if verified is not None:
                conditions.append(Event.verified == verified)
            if from_ts:
                conditions.append(Event.start_ts >= from_ts)
            if to_ts:
                conditions.append(Event.start_ts <= to_ts)

            if conditions:
                query = query.where(and_(*conditions))
                count_query = count_query.where(and_(*conditions))

            # Get total count
            count_result = await session.execute(count_query)
            total = len(count_result.scalars().all())

            # Apply pagination and ordering
            query = query.order_by(desc(Event.start_ts))
            query = query.offset((page - 1) * page_size).limit(page_size)

            result = await session.execute(query)
            events = list(result.scalars().all())

            return events, total

    async def get_event(self, event_id: str) -> Optional[Event]:
        """Get a single event by ID."""
        async with async_session() as session:
            result = await session.execute(
                select(Event).where(Event.id == event_id)
            )
            return result.scalar_one_or_none()

    async def verify_event(self, event_id: str, verified: bool) -> Optional[Event]:
        """Mark an event as verified or rejected."""
        async with async_session() as session:
            result = await session.execute(
                select(Event).where(Event.id == event_id)
            )
            event = result.scalar_one_or_none()
            if event:
                event.verified = verified
                await session.commit()
                await session.refresh(event)
            return event

    async def add_note(self, event_id: str, note: str) -> Optional[Event]:
        """Add a note to an event."""
        async with async_session() as session:
            result = await session.execute(
                select(Event).where(Event.id == event_id)
            )
            event = result.scalar_one_or_none()
            if event:
                event.note = note
                await session.commit()
                await session.refresh(event)
            return event

    async def delete_event(self, event_id: str) -> bool:
        """Delete an event."""
        async with async_session() as session:
            result = await session.execute(
                select(Event).where(Event.id == event_id)
            )
            event = result.scalar_one_or_none()
            if event:
                await session.delete(event)
                await session.commit()
                return True
            return False

    def event_to_response(self, event: Event) -> EventResponse:
        """Convert database event to response schema."""
        return EventResponse(
            id=event.id,
            camera_id=event.camera_id,
            track_id=event.track_id,
            start_ts=event.start_ts,
            end_ts=event.end_ts,
            sequence=event.get_sequence_list(),
            confidence=event.confidence or 0.0,
            snapshot_path=event.snapshot_path,
            clip_path=event.clip_path,
            verified=event.verified,
            note=event.note,
            created_at=event.created_at,
        )


# Global singleton instance
event_service = EventService()
