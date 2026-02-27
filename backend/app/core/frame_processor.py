"""Frame processor: YOLO + MoveNet run every frame; LLM runs periodically as fallback."""

import asyncio
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from uuid import uuid4

import cv2
import numpy as np

from app.api.schemas import (
    ActionResult,
    ActionSignals,
    ActionState,
    DetectionFrame,
    PersonDetection,
    SystemStatus,
)
from app.config import settings
from app.core.ring_buffer import RingBuffer
from app.core.state_machine import ActionStateMachine
from app.core.video_capture import VideoCapture, create_capture
from app.detection.llm_detector import VisionLLMDetector
from app.detection.movenet_detector import MoveNetDetector
from app.detection.overlay import OverlayRenderer
from app.detection.yolo_detector import YOLODetector


class FrameProcessor:
    """
    Per-camera processing pipeline.

    _frame_loop  (fast, every frame):
        capture → YOLO (bbox) + MoveNet (pose) in parallel threads
        → heuristic action (PRIMARY) → merge overlay → MJPEG push

    _detection_loop (slow, ~500 ms):
        crop person → LLM classify action (SECONDARY / confirmation)
        → updates _last_llm_detection

    Merge priority:
        MoveNet action used when confidence >= movenet_confidence_threshold,
        otherwise LLM action is shown.
    """

    def __init__(
        self,
        camera_id: str,
        source: str,
        source_type: str,
        on_event_completed: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_frame_processed: Optional[Callable[[DetectionFrame], None]] = None,
    ):
        self.camera_id = camera_id
        self.source = source
        self.source_type = source_type
        self.on_event_completed = on_event_completed
        self.on_frame_processed = on_frame_processed

        # Pipeline components
        self._capture: Optional[VideoCapture] = None
        self._yolo = YOLODetector()
        self._movenet = MoveNetDetector()
        self._llm: Optional[VisionLLMDetector] = None
        self._state_machine = ActionStateMachine()
        self._overlay = OverlayRenderer()
        self._ring_buffer = RingBuffer()

        # Running state
        self._running = False
        self._status = "stopped"
        self._movenet_active = False   # True once model is loaded

        # Metrics
        self._frame_count = 0
        self._fps_counter = 0
        self._fps_start_time = time.time()
        self._current_fps = 0.0
        self._last_detection_time = 0.0

        # Shared state between loops (GIL protects simple assignments)
        self._latest_raw_frame: Optional[np.ndarray] = None
        self._latest_yolo_detections: List[PersonDetection] = []

        # PRIMARY: last MoveNet-based detection (updated every frame)
        self._last_movenet_detection: Optional[PersonDetection] = None
        # SECONDARY: last LLM-based detection (updated ~every 500 ms)
        self._last_llm_detection: Optional[PersonDetection] = None

        # Event banner
        self._last_event_time: float = 0.0
        self._event_banner_duration: float = 5.0

        # Current annotated frame + event to signal MJPEG consumers
        self._current_frame: Optional[np.ndarray] = None
        self._frame_event: asyncio.Event = asyncio.Event()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> bool:
        if self._running:
            return True

        self._capture = create_capture(self.source, self.source_type)
        if not self._capture.start():
            self._status = "error"
            return False

        # Warmup YOLO (first real inference would otherwise be slow)
        await asyncio.to_thread(self._yolo.warmup)

        # Load MoveNet model (downloads if not cached) — non-blocking via thread
        self._movenet_active = await asyncio.to_thread(self._movenet.load)
        if self._movenet_active:
            print("MoveNet Lightning loaded — local action detection ACTIVE")
        else:
            print("Warning: MoveNet unavailable — falling back to LLM-only action detection")

        # Initialise LLM (secondary / fallback)
        self._llm = VisionLLMDetector()
        try:
            await self._llm.initialize()
        except Exception as e:
            print(f"Warning: LLM init failed: {e}")

        self._running = True
        self._status = "live"
        self._fps_start_time = time.time()

        asyncio.create_task(self._frame_loop())
        asyncio.create_task(self._detection_loop())

        return True

    async def stop(self):
        self._running = False
        self._status = "stopped"
        if self._capture:
            self._capture.stop()
            self._capture = None
        if self._llm:
            await self._llm.close()
            self._llm = None

    # ------------------------------------------------------------------
    # Frame loop — runs at camera speed; YOLO + MoveNet every frame
    # ------------------------------------------------------------------

    async def _frame_loop(self):
        while self._running and self._capture and self._capture.is_opened():
            success, frame, timestamp = self._capture.get_frame()
            if not success or frame is None:
                await asyncio.sleep(0.005)
                continue

            self._frame_count += 1
            self._fps_counter += 1
            self._latest_raw_frame = frame

            self._ring_buffer.add_frame(frame, timestamp)

            # ── Run YOLO and MoveNet concurrently in threads ───────────────────
            try:
                if self._movenet_active:
                    yolo_dets, kp = await asyncio.gather(
                        asyncio.to_thread(self._yolo.detect, frame),
                        asyncio.to_thread(self._movenet.infer, frame),
                    )
                else:
                    yolo_dets = await asyncio.to_thread(self._yolo.detect, frame)
                    kp = None

                self._latest_yolo_detections = yolo_dets

                # Classify MoveNet action for primary person
                if yolo_dets:
                    primary = yolo_dets[0]
                    mn_state, mn_conf, mn_signals = self._movenet.classify_action(
                        kp, primary.bottle_bbox
                    )
                    self._last_movenet_detection = PersonDetection(
                        track_id=primary.track_id,
                        person_bbox=primary.person_bbox,
                        bottle_bbox=primary.bottle_bbox,
                        action=ActionResult(
                            state=mn_state,
                            confidence=mn_conf,
                            signals=mn_signals,
                        ),
                    )
                else:
                    self._last_movenet_detection = None

            except Exception as e:
                print(f"Frame detection error: {e}")
                yolo_dets = self._latest_yolo_detections

            # FPS counter
            fps_elapsed = time.time() - self._fps_start_time
            if fps_elapsed >= 1.0:
                self._current_fps = self._fps_counter / fps_elapsed
                self._fps_counter = 0
                self._fps_start_time = time.time()

            # Merge fresh YOLO bboxes with best available action
            merged = self._merge_detections(yolo_dets)

            latency_ms = (
                int((time.time() - self._last_detection_time) * 1000)
                if self._last_detection_time
                else 0
            )
            event_active = (
                self._last_event_time > 0
                and (time.time() - self._last_event_time) < self._event_banner_duration
            )

            annotated = self._overlay.render(
                frame,
                merged,
                fps=self._current_fps,
                latency_ms=latency_ms,
                status=self._status,
                event_active=event_active,
            )

            self._current_frame = annotated
            self._frame_event.set()

            # WebSocket broadcast
            if self.on_frame_processed and merged:
                detection_frame = DetectionFrame(
                    ts=datetime.utcnow(),
                    camera_id=self.camera_id,
                    frame_id=self._frame_count,
                    people=merged,
                    system=SystemStatus(
                        fps=self._current_fps,
                        latency_ms=latency_ms,
                        status=self._status,
                    ),
                )
                try:
                    self.on_frame_processed(detection_frame)
                except Exception as e:
                    print(f"WS callback error: {e}")

            # ── State machine tick (uses best available action) ────────────────
            best = self._last_movenet_detection or self._last_llm_detection
            if best and best.action.state not in (ActionState.IDLE, ActionState.UNCERTAIN):
                _, is_completed, event_data = self._state_machine.update(
                    best.track_id, best.action.state, best.action.confidence
                )
                if is_completed and event_data:
                    self._last_event_time = time.time()
                    asyncio.create_task(
                        self._handle_event_completed(event_data, frame)
                    )

            await asyncio.sleep(0)

    # ------------------------------------------------------------------
    # Detection loop — LLM secondary, runs every ~500 ms
    # ------------------------------------------------------------------

    async def _detection_loop(self):
        min_gap = settings.detection_interval_ms / 1000.0

        # Wait for first frame
        while self._running and self._latest_raw_frame is None:
            await asyncio.sleep(0.05)

        while self._running:
            if not self._llm:
                break

            call_start = time.time()

            frame = self._latest_raw_frame
            yolo_dets = self._latest_yolo_detections

            if frame is None:
                await asyncio.sleep(0.05)
                continue

            try:
                primary = yolo_dets[0] if yolo_dets else None

                if primary and primary.person_bbox:
                    crop = self._llm.crop_region(frame, primary.person_bbox)
                    state, confidence = await self._llm.detect_action(
                        crop, bottle_detected=primary.bottle_bbox is not None
                    )
                    self._last_llm_detection = PersonDetection(
                        track_id=primary.track_id,
                        person_bbox=primary.person_bbox,
                        bottle_bbox=primary.bottle_bbox,
                        action=ActionResult(
                            state=state,
                            confidence=confidence,
                            signals=ActionSignals(),
                        ),
                    )
                else:
                    detection = await self._llm.detect(frame)
                    self._last_llm_detection = detection

                self._last_detection_time = time.time()

            except Exception as e:
                print(f"LLM detection error: {e}")

            elapsed = time.time() - call_start
            remaining = min_gap - elapsed
            if remaining > 0:
                await asyncio.sleep(remaining)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    _MOVENET_MIN_CONF = 0.45   # use MoveNet action when its confidence ≥ this

    def _merge_detections(
        self, yolo_dets: List[PersonDetection]
    ) -> List[PersonDetection]:
        """
        Build the display list:
          - Fresh YOLO bboxes (always up to date)
          - Action: MoveNet PRIMARY if confident, else LLM SECONDARY, else IDLE

        For cap_opening / drinking specifically:
          - LLM may override MoveNet if LLM confidence is higher and MoveNet
            is below threshold (LLM acts as confirmation for subtle gestures).
        """
        movenet = self._last_movenet_detection
        llm     = self._last_llm_detection

        if not yolo_dets:
            # No YOLO detection — show cached result if any
            best = movenet or llm
            return [best] if best else []

        merged: List[PersonDetection] = []
        for det in yolo_dets:
            action = self._pick_action(det, movenet, llm, len(yolo_dets))
            merged.append(
                PersonDetection(
                    track_id=det.track_id,
                    person_bbox=det.person_bbox,
                    bottle_bbox=det.bottle_bbox,
                    action=action,
                )
            )
        return merged

    def _pick_action(
        self,
        det: PersonDetection,
        movenet: Optional[PersonDetection],
        llm: Optional[PersonDetection],
        n_persons: int,
    ) -> ActionResult:
        """Choose the best action for this detection."""
        id_match = lambda cached: (
            cached is not None
            and (det.track_id == cached.track_id or n_persons == 1)
        )

        mn_action  = movenet.action if id_match(movenet) else None
        llm_action = llm.action     if id_match(llm)     else None

        # MoveNet is primary — use if above threshold
        if mn_action and mn_action.confidence >= self._MOVENET_MIN_CONF:
            # For subtle states (cap_opening / drinking) also check LLM agreement
            if mn_action.state in (ActionState.CAP_OPENING, ActionState.DRINKING):
                if llm_action and llm_action.state == mn_action.state:
                    # Both agree — boost confidence
                    boosted_conf = min(1.0, (mn_action.confidence + llm_action.confidence) / 2 + 0.1)
                    return ActionResult(
                        state=mn_action.state,
                        confidence=boosted_conf,
                        signals=mn_action.signals,
                    )
                # MoveNet alone above threshold — trust it
                if mn_action.confidence >= 0.60:
                    return mn_action
                # MoveNet marginal + LLM disagrees — fall through to LLM
            else:
                return mn_action

        # LLM secondary
        if llm_action:
            return llm_action

        # Default: IDLE from YOLO detection
        return det.action

    async def _handle_event_completed(
        self, event_data: Dict[str, Any], current_frame: np.ndarray
    ):
        event_id = str(uuid4())
        start_ts = event_data.get("start_ts")
        end_ts   = event_data.get("end_ts")

        if not start_ts or not end_ts:
            return

        start_time = start_ts.timestamp() if hasattr(start_ts, "timestamp") else start_ts
        end_time   = end_ts.timestamp()   if hasattr(end_ts,   "timestamp") else end_ts

        snapshot_path = settings.snapshots_dir / f"{event_id}.jpg"
        self._ring_buffer.save_snapshot(snapshot_path, current_frame)

        clip_path   = settings.clips_dir / f"{event_id}.mp4"
        clip_frames = self._ring_buffer.get_clip_frames(start_time, end_time)
        if clip_frames:
            self._ring_buffer.save_clip(clip_path, clip_frames)

        event_data["id"]            = event_id
        event_data["camera_id"]     = self.camera_id
        event_data["snapshot_path"] = str(snapshot_path)
        event_data["clip_path"]     = str(clip_path) if clip_frames else None

        if self.on_event_completed:
            try:
                result = self.on_event_completed(event_data)
                if asyncio.iscoroutine(result):
                    asyncio.create_task(result)
            except Exception as e:
                print(f"Event callback error: {e}")

    def get_mjpeg_frame(self) -> Optional[bytes]:
        if self._current_frame is None:
            return None
        try:
            _, jpeg = cv2.imencode(
                ".jpg",
                self._current_frame,
                [cv2.IMWRITE_JPEG_QUALITY, settings.mjpeg_quality],
            )
            return jpeg.tobytes()
        except Exception:
            return None

    @property
    def frame_event(self) -> asyncio.Event:
        return self._frame_event

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def status(self) -> str:
        return self._status

    @property
    def fps(self) -> float:
        return self._current_fps

    @property
    def frame_count(self) -> int:
        return self._frame_count
