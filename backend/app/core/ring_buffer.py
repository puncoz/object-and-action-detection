"""Ring buffer for storing video frames for clip saving."""

import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.config import settings


@dataclass
class BufferedFrame:
    """A frame stored in the ring buffer."""
    frame: np.ndarray
    timestamp: float
    frame_id: int


class RingBuffer:
    """
    Circular buffer for storing recent video frames.

    Used to save video clips of detected events (N seconds before + after).
    """

    def __init__(
        self,
        duration_seconds: int = settings.ring_buffer_duration_sec,
        fps: int = settings.default_fps,
    ):
        self.duration_seconds = duration_seconds
        self.fps = fps
        self.max_frames = duration_seconds * fps
        self._buffer: deque[BufferedFrame] = deque(maxlen=self.max_frames)
        self._lock = threading.Lock()
        self._frame_counter = 0

    def add_frame(self, frame: np.ndarray, timestamp: Optional[float] = None) -> int:
        """
        Add a frame to the buffer.

        Args:
            frame: Video frame (BGR)
            timestamp: Optional timestamp, uses current time if not provided

        Returns:
            Frame ID
        """
        if timestamp is None:
            timestamp = time.time()

        with self._lock:
            self._frame_counter += 1
            buffered = BufferedFrame(
                frame=frame.copy(),
                timestamp=timestamp,
                frame_id=self._frame_counter,
            )
            self._buffer.append(buffered)
            return self._frame_counter

    def get_frames_in_range(
        self,
        start_time: float,
        end_time: float,
    ) -> List[BufferedFrame]:
        """
        Get frames within a time range.

        Args:
            start_time: Start timestamp (Unix time)
            end_time: End timestamp (Unix time)

        Returns:
            List of frames in the range
        """
        with self._lock:
            frames = [
                f for f in self._buffer
                if start_time <= f.timestamp <= end_time
            ]
        return frames

    def get_clip_frames(
        self,
        event_start: float,
        event_end: float,
        before_sec: int = settings.clip_before_sec,
        after_sec: int = settings.clip_after_sec,
    ) -> List[BufferedFrame]:
        """
        Get frames for a clip around an event.

        Args:
            event_start: Event start timestamp
            event_end: Event end timestamp
            before_sec: Seconds before event to include
            after_sec: Seconds after event to include

        Returns:
            List of frames for the clip
        """
        clip_start = event_start - before_sec
        clip_end = event_end + after_sec
        return self.get_frames_in_range(clip_start, clip_end)

    def save_clip(
        self,
        output_path: Path,
        frames: List[BufferedFrame],
        fps: Optional[int] = None,
    ) -> bool:
        """
        Save frames as a video clip.

        Args:
            output_path: Output file path (.mp4)
            frames: List of frames to save
            fps: Output FPS (uses buffer FPS if not provided)

        Returns:
            True if successful
        """
        if not frames:
            return False

        fps = fps or self.fps
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Get frame dimensions from first frame
        h, w = frames[0].frame.shape[:2]

        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        writer = cv2.VideoWriter(str(output_path), fourcc, fps, (w, h))

        if not writer.isOpened():
            return False

        try:
            for buffered in frames:
                writer.write(buffered.frame)
            return True
        finally:
            writer.release()

    def save_snapshot(
        self,
        output_path: Path,
        frame: np.ndarray,
        quality: int = 90,
    ) -> bool:
        """
        Save a single frame as a snapshot image.

        Args:
            output_path: Output file path (.jpg)
            frame: Frame to save
            quality: JPEG quality (0-100)

        Returns:
            True if successful
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            cv2.imwrite(
                str(output_path),
                frame,
                [cv2.IMWRITE_JPEG_QUALITY, quality],
            )
            return True
        except Exception:
            return False

    def get_current_frame(self) -> Optional[BufferedFrame]:
        """Get the most recent frame."""
        with self._lock:
            if self._buffer:
                return self._buffer[-1]
        return None

    def get_buffer_duration(self) -> float:
        """Get the current duration of buffered content in seconds."""
        with self._lock:
            if len(self._buffer) < 2:
                return 0.0
            return self._buffer[-1].timestamp - self._buffer[0].timestamp

    def clear(self):
        """Clear the buffer."""
        with self._lock:
            self._buffer.clear()
            self._frame_counter = 0

    def __len__(self) -> int:
        """Get number of frames in buffer."""
        return len(self._buffer)
