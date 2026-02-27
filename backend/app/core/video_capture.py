"""Video capture abstraction for different source types."""

import time
from abc import ABC, abstractmethod
from typing import Optional, Tuple
import threading
import queue

import cv2
import numpy as np

from app.config import settings


class VideoCapture(ABC):
    """Abstract base class for video capture."""

    @abstractmethod
    def start(self) -> bool:
        """Start capturing video."""
        pass

    @abstractmethod
    def stop(self):
        """Stop capturing video."""
        pass

    @abstractmethod
    def get_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """Get the next frame. Returns (success, frame, timestamp)."""
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """Check if capture is open."""
        pass

    @property
    @abstractmethod
    def fps(self) -> float:
        """Get frames per second."""
        pass

    @property
    @abstractmethod
    def frame_size(self) -> Tuple[int, int]:
        """Get frame size (width, height)."""
        pass


class OpenCVCapture(VideoCapture):
    """OpenCV-based video capture for webcam, file, and RTSP."""

    def __init__(
        self,
        source: str,
        source_type: str,
        width: int = settings.frame_width,
        height: int = settings.frame_height,
        target_fps: int = settings.default_fps,
    ):
        self.source = source
        self.source_type = source_type
        self.width = width
        self.height = height
        self.target_fps = target_fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._fps = target_fps
        self._frame_size = (width, height)
        self._running = False
        self._loop_video = source_type == "file"  # Loop file sources for demo

    def start(self) -> bool:
        """Start the video capture."""
        try:
            # Determine source for OpenCV
            if self.source_type == "webcam":
                source = int(self.source) if self.source.isdigit() else 0
            else:
                source = self.source

            self._cap = cv2.VideoCapture(source)

            if not self._cap.isOpened():
                return False

            # Set resolution for webcam
            if self.source_type == "webcam":
                self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
                self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
                # Request higher buffer count for lower latency
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

            # Get actual FPS from source
            source_fps = self._cap.get(cv2.CAP_PROP_FPS)
            if source_fps > 0:
                self._fps = min(source_fps, self.target_fps)

            # Get actual frame size
            actual_width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            if actual_width > 0 and actual_height > 0:
                self._frame_size = (actual_width, actual_height)

            self._running = True
            return True

        except Exception as e:
            print(f"Error starting capture: {e}")
            return False

    def stop(self):
        """Stop the video capture."""
        self._running = False
        if self._cap:
            self._cap.release()
            self._cap = None

    def get_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """Get the next frame."""
        if not self._cap or not self._running:
            return False, None, 0.0

        ret, frame = self._cap.read()
        timestamp = time.time()

        # Handle looping for file sources
        if not ret and self._loop_video and self.source_type == "file":
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()

        if ret and frame is not None:
            # Resize if needed
            if frame.shape[1] != self.width or frame.shape[0] != self.height:
                frame = cv2.resize(frame, (self.width, self.height))

        return ret, frame, timestamp

    def is_opened(self) -> bool:
        """Check if capture is open."""
        return self._cap is not None and self._cap.isOpened() and self._running

    @property
    def fps(self) -> float:
        """Get frames per second."""
        return self._fps

    @property
    def frame_size(self) -> Tuple[int, int]:
        """Get frame size (width, height)."""
        return self._frame_size


class BufferedCapture(VideoCapture):
    """Threaded video capture with minimal-latency frame buffering."""

    def __init__(
        self,
        source: str,
        source_type: str,
        width: int = settings.frame_width,
        height: int = settings.frame_height,
        target_fps: int = settings.default_fps,
        buffer_size: int = 2,  # Minimal buffer — keep only the 2 most recent frames
    ):
        self._inner = OpenCVCapture(
            source, source_type, width, height, target_fps)
        self._buffer: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._thread: Optional[threading.Thread] = None
        self._running = False

    def _capture_loop(self):
        """Background thread for capturing frames as fast as possible."""
        while self._running:
            ret, frame, timestamp = self._inner.get_frame()
            if ret and frame is not None:
                # Always keep only the latest frame: drop oldest if buffer full
                if self._buffer.full():
                    try:
                        self._buffer.get_nowait()
                    except queue.Empty:
                        pass
                try:
                    self._buffer.put_nowait((frame, timestamp))
                except queue.Full:
                    pass
            else:
                time.sleep(0.005)

    def start(self) -> bool:
        """Start the buffered capture."""
        if not self._inner.start():
            return False

        self._running = True
        self._thread = threading.Thread(target=self._capture_loop, daemon=True)
        self._thread.start()
        return True

    def stop(self):
        """Stop the buffered capture."""
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        self._inner.stop()

    def get_frame(self) -> Tuple[bool, Optional[np.ndarray], float]:
        """Get the latest available frame — non-blocking."""
        try:
            frame, timestamp = self._buffer.get_nowait()
            return True, frame, timestamp
        except queue.Empty:
            return False, None, 0.0

    def is_opened(self) -> bool:
        """Check if capture is open."""
        return self._running and self._inner.is_opened()

    @property
    def fps(self) -> float:
        """Get frames per second."""
        return self._inner.fps

    @property
    def frame_size(self) -> Tuple[int, int]:
        """Get frame size (width, height)."""
        return self._inner.frame_size


def create_capture(source: str, source_type: str, buffered: bool = True) -> VideoCapture:
    """Factory function to create appropriate video capture."""
    if buffered:
        return BufferedCapture(source, source_type)
    return OpenCVCapture(source, source_type)
