"""Database setup and models for Factory Action Console."""

import json
from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    create_engine,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, relationship

from app.config import settings


class Base(DeclarativeBase):
    """Base class for all database models."""
    pass


class Camera(Base):
    """Camera model for tracking video sources."""

    __tablename__ = "cameras"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    name = Column(String, nullable=False)
    # RTSP URL, file path, or device index
    source = Column(String, nullable=False)
    type = Column(String, nullable=False)  # 'rtsp', 'file', 'webcam'
    status = Column(String, default="stopped")  # 'running', 'stopped', 'error'
    created_at = Column(DateTime, default=datetime.utcnow)

    events = relationship("Event", back_populates="camera")


class Event(Base):
    """Event model for storing hydration detection events."""

    __tablename__ = "events"

    id = Column(String, primary_key=True, default=lambda: str(uuid4()))
    camera_id = Column(String, ForeignKey("cameras.id"), nullable=False)
    track_id = Column(Integer, default=0)
    start_ts = Column(DateTime, nullable=False)
    end_ts = Column(DateTime, nullable=True)
    sequence = Column(Text, nullable=True)  # JSON array of states
    confidence = Column(Float, nullable=True)
    snapshot_path = Column(String, nullable=True)
    clip_path = Column(String, nullable=True)
    # None=pending, True=verified, False=rejected
    verified = Column(Boolean, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    camera = relationship("Camera", back_populates="events")

    __table_args__ = (
        Index("idx_events_camera", "camera_id"),
        Index("idx_events_ts", "start_ts"),
        Index("idx_events_verified", "verified"),
    )

    def get_sequence_list(self) -> list[str]:
        """Get sequence as a list."""
        if self.sequence:
            return json.loads(self.sequence)
        return []

    def set_sequence_list(self, states: list[str]):
        """Set sequence from a list."""
        self.sequence = json.dumps(states)


# Create async engine
engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
)

# Create session factory
async_session = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def init_db():
    """Initialize database tables."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get a database session."""
    async with async_session() as session:
        yield session
