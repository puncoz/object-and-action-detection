"""Pydantic schemas for API requests and responses."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# === Enums ===

class CameraType(str, Enum):
    """Camera source types."""
    RTSP = "rtsp"
    FILE = "file"
    WEBCAM = "webcam"


class CameraStatus(str, Enum):
    """Camera processing status."""
    RUNNING = "running"
    STOPPED = "stopped"
    ERROR = "error"


class ActionState(str, Enum):
    """Hydration action states."""
    IDLE = "idle"
    BOTTLE_IN_HAND = "bottle_in_hand"
    CAP_OPENING = "cap_opening"
    DRINKING = "drinking"
    COMPLETED = "completed"
    UNCERTAIN = "uncertain"


# === Camera Schemas ===

class CameraCreate(BaseModel):
    """Schema for creating a camera."""
    name: str = Field(..., min_length=1, max_length=100)
    source: str = Field(..., min_length=1)
    type: CameraType


class CameraResponse(BaseModel):
    """Schema for camera response."""
    id: str
    name: str
    source: str
    type: CameraType
    status: CameraStatus
    created_at: datetime

    class Config:
        from_attributes = True


class CameraListResponse(BaseModel):
    """Schema for list of cameras."""
    cameras: list[CameraResponse]
    total: int


# === Detection Schemas ===

class BoundingBox(BaseModel):
    """Bounding box coordinates."""
    x1: float
    y1: float
    x2: float
    y2: float


class DetectedObject(BaseModel):
    """A single detected non-person object."""
    class_id: int
    class_name: str
    bbox: BoundingBox
    confidence: float
    track_id: Optional[int] = None


class PoseKeypoint(BaseModel):
    """Single MoveNet keypoint in normalised image coordinates."""
    x: float    # normalised 0-1
    y: float    # normalised 0-1
    conf: float


class ActionSignals(BaseModel):
    """Detection signals contributing to action state."""
    hand_bottle_proximity: float = 0.0
    neck_hand_proximity: float = 0.0
    wrist_rotation: float = 0.0
    mouth_bottle_proximity: float = 0.0
    bottle_tilt: float = 0.0


class ActionResult(BaseModel):
    """Action detection result."""
    state: ActionState
    confidence: float = Field(..., ge=0.0, le=1.0)
    signals: ActionSignals = Field(default_factory=ActionSignals)
    activity: str = ""


class PersonDetection(BaseModel):
    """Detection result for a single person."""
    track_id: int = 0
    person_bbox: Optional[BoundingBox] = None
    bottle_bbox: Optional[BoundingBox] = None
    action: ActionResult
    nearby_objects: list[DetectedObject] = []
    pose: Optional[list[PoseKeypoint]] = None


class SystemStatus(BaseModel):
    """System performance metrics."""
    fps: float
    latency_ms: int
    status: str  # 'live', 'delayed', 'offline'


class DetectionFrame(BaseModel):
    """Full detection result for a frame."""
    ts: datetime
    camera_id: str
    frame_id: int
    people: list[PersonDetection]
    objects: list[DetectedObject] = []
    system: SystemStatus


# === Event Schemas ===

class EventCreate(BaseModel):
    """Schema for creating an event (internal use)."""
    camera_id: str
    track_id: int = 0
    start_ts: datetime
    end_ts: Optional[datetime] = None
    sequence: list[str] = []
    confidence: float = 0.0


class EventResponse(BaseModel):
    """Schema for event response."""
    id: str
    camera_id: str
    track_id: int
    start_ts: datetime
    end_ts: Optional[datetime]
    sequence: list[str]
    confidence: float
    snapshot_path: Optional[str]
    clip_path: Optional[str]
    verified: Optional[bool]
    note: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class EventListResponse(BaseModel):
    """Schema for list of events."""
    events: list[EventResponse]
    total: int
    page: int
    page_size: int


class EventVerify(BaseModel):
    """Schema for verifying an event."""
    verified: bool


class EventNote(BaseModel):
    """Schema for adding a note to an event."""
    note: str = Field(..., max_length=1000)


# === WebSocket Messages ===

class WSMessage(BaseModel):
    """WebSocket message wrapper."""
    type: str  # 'detection', 'event', 'status', 'error'
    data: dict
