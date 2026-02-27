"""Overlay rendering for detection visualization."""

from typing import List, Optional, Tuple
import cv2
import numpy as np

from app.api.schemas import (
    ActionState,
    BoundingBox,
    DetectedObject,
    PersonDetection,
    PoseKeypoint,
)


# Color scheme (BGR format for OpenCV)
COLORS = {
    "person": (255, 200, 100),      # Light blue
    "bottle": (100, 255, 100),      # Green
    "text_bg": (40, 40, 40),        # Dark gray
    "text": (255, 255, 255),        # White
    "progress_bg": (60, 60, 60),    # Gray
    "progress_active": (100, 255, 100),   # Green
    "progress_inactive": (100, 100, 100),  # Gray
}

STATE_COLORS = {
    ActionState.IDLE: (150, 150, 150),        # Gray
    ActionState.BOTTLE_IN_HAND: (100, 200, 255),  # Orange
    ActionState.CAP_OPENING: (100, 255, 255),     # Yellow
    ActionState.DRINKING: (100, 255, 100),        # Green
    ActionState.COMPLETED: (255, 100, 255),       # Magenta
    ActionState.UNCERTAIN: (100, 100, 255),       # Red
}

STATE_LABELS = {
    ActionState.IDLE: "Idle",
    ActionState.BOTTLE_IN_HAND: "Holding Bottle",
    ActionState.CAP_OPENING: "Opening Cap",
    ActionState.DRINKING: "Drinking",
    ActionState.COMPLETED: "Completed!",
    ActionState.UNCERTAIN: "Uncertain",
}

# ── Skeleton constants ────────────────────────────────────────────────────────

# MoveNet keypoint indices
_KP_NOSE, _KP_L_EYE, _KP_R_EYE, _KP_L_EAR, _KP_R_EAR = 0, 1, 2, 3, 4
_KP_L_SHOULDER, _KP_R_SHOULDER = 5, 6
_KP_L_ELBOW, _KP_R_ELBOW = 7, 8
_KP_L_WRIST, _KP_R_WRIST = 9, 10
_KP_L_HIP, _KP_R_HIP = 11, 12
_KP_L_KNEE, _KP_R_KNEE = 13, 14
_KP_L_ANKLE, _KP_R_ANKLE = 15, 16

# Skeleton connections (source_idx, dest_idx)
_SKELETON: List[Tuple[int, int]] = [
    (_KP_NOSE, _KP_L_EYE), (_KP_NOSE, _KP_R_EYE),
    (_KP_L_EYE, _KP_L_EAR), (_KP_R_EYE, _KP_R_EAR),
    (_KP_L_SHOULDER, _KP_R_SHOULDER),
    (_KP_L_SHOULDER, _KP_L_ELBOW), (_KP_L_ELBOW, _KP_L_WRIST),
    (_KP_R_SHOULDER, _KP_R_ELBOW), (_KP_R_ELBOW, _KP_R_WRIST),
    (_KP_L_SHOULDER, _KP_L_HIP), (_KP_R_SHOULDER, _KP_R_HIP),
    (_KP_L_HIP, _KP_R_HIP),
    (_KP_L_HIP, _KP_L_KNEE), (_KP_L_KNEE, _KP_L_ANKLE),
    (_KP_R_HIP, _KP_R_KNEE), (_KP_R_KNEE, _KP_R_ANKLE),
]

# Keypoint colour by index (BGR) — head=cyan, L-arm=yellow, R-arm=orange,
#   torso=white, L-leg=lime, R-leg=green
_KP_COLORS: List[Tuple[int, int, int]] = [
    (255, 255, 0),   # 0  nose        cyan
    (255, 255, 0),   # 1  L_eye       cyan
    (255, 255, 0),   # 2  R_eye       cyan
    (255, 255, 0),   # 3  L_ear       cyan
    (255, 255, 0),   # 4  R_ear       cyan
    (0, 255, 255),   # 5  L_shoulder  yellow
    (0, 165, 255),   # 6  R_shoulder  orange
    (0, 255, 255),   # 7  L_elbow     yellow
    (0, 165, 255),   # 8  R_elbow     orange
    (0, 255, 255),   # 9  L_wrist     yellow
    (0, 165, 255),   # 10 R_wrist     orange
    (255, 255, 255), # 11 L_hip       white
    (255, 255, 255), # 12 R_hip       white
    (0, 255, 0),     # 13 L_knee      lime
    (0, 200, 0),     # 14 R_knee      green
    (0, 255, 0),     # 15 L_ankle     lime
    (0, 200, 0),     # 16 R_ankle     green
]

_KP_CONF_DRAW = 0.25   # minimum keypoint confidence to draw


def _object_color(class_name: str) -> Tuple[int, int, int]:
    """Deterministic BGR colour from class name; each channel ≥ 120 for visibility."""
    h = abs(hash(class_name))
    r = max(120, (h >> 16) & 0xFF)
    g = max(120, (h >> 8) & 0xFF)
    b = max(120, h & 0xFF)
    return (b, g, r)


class OverlayRenderer:
    """Renders detection overlays on video frames."""

    def __init__(
        self,
        show_person_bbox: bool = True,
        show_bottle_bbox: bool = True,
        show_action_label: bool = True,
        show_progress: bool = True,
        show_fps: bool = True,
        confidence_threshold: float = 0.3,
    ):
        self.show_person_bbox = show_person_bbox
        self.show_bottle_bbox = show_bottle_bbox
        self.show_action_label = show_action_label
        self.show_progress = show_progress
        self.show_fps = show_fps
        self.confidence_threshold = confidence_threshold

    def render(
        self,
        frame: np.ndarray,
        detections: List[PersonDetection],
        objects: List[DetectedObject] = [],
        fps: float = 0.0,
        latency_ms: int = 0,
        status: str = "live",
        event_active: bool = False,
    ) -> np.ndarray:
        """
        Render all overlays on the frame.

        Args:
            frame: Input frame (BGR)
            detections: List of person detections
            objects: Standalone detected objects (not near any person)
            fps: Current FPS
            latency_ms: Detection latency in ms
            status: System status string
            event_active: Show hydration-detected event banner

        Returns:
            Frame with overlays drawn
        """
        output = frame.copy()

        # Draw standalone objects first (behind person overlays)
        for obj in objects:
            self._draw_detected_object(output, obj)

        # Draw person detections
        for detection in detections:
            self._draw_person_detection(output, detection)

        # Draw system status
        if self.show_fps:
            self._draw_system_status(output, fps, latency_ms, status)

        # Draw event banner on top of everything else
        if event_active:
            self._draw_event_banner(output)

        return output

    def _draw_person_detection(self, frame: np.ndarray, detection: PersonDetection):
        """Draw detection overlays for a single person."""
        h, w = frame.shape[:2]

        # Draw nearby non-person objects
        for obj in detection.nearby_objects:
            self._draw_detected_object(frame, obj)

        # Draw skeleton if pose is available
        if detection.pose:
            self._draw_skeleton(frame, detection.pose)

        # Draw person bounding box
        if self.show_person_bbox and detection.person_bbox:
            self._draw_bbox(
                frame,
                detection.person_bbox,
                COLORS["person"],
                f"Person {detection.track_id}",
            )

        # Draw action label and progress
        if detection.action.confidence >= self.confidence_threshold:
            state = detection.action.state
            confidence = detection.action.confidence

            # Determine label position (above person bbox or top-left)
            if detection.person_bbox:
                label_x = int(detection.person_bbox.x1 * w)
                label_y = max(30, int(detection.person_bbox.y1 * h) - 60)
            else:
                label_x = 20
                label_y = 80 + detection.track_id * 100

            if self.show_action_label:
                self._draw_action_label(
                    frame, state, confidence, detection.action.activity,
                    label_x, label_y,
                )

            if self.show_progress:
                progress_y = label_y + 35
                if detection.action.activity:
                    progress_y += 22   # shift down to clear activity text
                self._draw_progress_bar(frame, state, label_x, progress_y)

    def _draw_detected_object(self, frame: np.ndarray, obj: DetectedObject):
        """Draw a non-person detected object with class label."""
        color = _object_color(obj.class_name)
        label = f"{obj.class_name} ({obj.confidence:.0%})"
        self._draw_bbox(frame, obj.bbox, color, label)

    def _draw_skeleton(self, frame: np.ndarray, pose: List[PoseKeypoint]):
        """Draw MoveNet skeleton from a list of 17 PoseKeypoints."""
        h, w = frame.shape[:2]

        # Draw limb connections first (behind circles)
        for src_idx, dst_idx in _SKELETON:
            src = pose[src_idx]
            dst = pose[dst_idx]
            if src.conf >= _KP_CONF_DRAW and dst.conf >= _KP_CONF_DRAW:
                pt1 = (int(src.x * w), int(src.y * h))
                pt2 = (int(dst.x * w), int(dst.y * h))
                cv2.line(frame, pt1, pt2, _KP_COLORS[src_idx], 2, cv2.LINE_AA)

        # Draw keypoint circles on top
        for i, kp in enumerate(pose):
            if kp.conf >= _KP_CONF_DRAW:
                cx = int(kp.x * w)
                cy = int(kp.y * h)
                cv2.circle(frame, (cx, cy), 4, _KP_COLORS[i], -1, cv2.LINE_AA)

    def _draw_bbox(
        self,
        frame: np.ndarray,
        bbox: BoundingBox,
        color: Tuple[int, int, int],
        label: str,
    ):
        """Draw a bounding box with label."""
        h, w = frame.shape[:2]

        x1 = int(bbox.x1 * w)
        y1 = int(bbox.y1 * h)
        x2 = int(bbox.x2 * w)
        y2 = int(bbox.y2 * h)

        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)

        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(
            frame,
            (x1, y1 - 20),
            (x1 + label_size[0] + 10, y1),
            color,
            -1,
        )
        cv2.putText(
            frame,
            label,
            (x1 + 5, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 0, 0),
            1,
            cv2.LINE_AA,
        )

    def _draw_action_label(
        self,
        frame: np.ndarray,
        state: ActionState,
        confidence: float,
        activity: str,
        x: int,
        y: int,
    ):
        """Draw action state label with confidence, and optional activity line."""
        label = f"{STATE_LABELS.get(state, state.value)} ({confidence:.0%})"
        color = STATE_COLORS.get(state, COLORS["text"])

        # Background covers the action label (and activity line if present)
        label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)
        bg_h = 30 + (22 if activity else 0)
        cv2.rectangle(
            frame,
            (x - 5, y - 25),
            (x + label_size[0] + 10, y + bg_h - 25),
            COLORS["text_bg"],
            -1,
        )

        cv2.putText(
            frame,
            label,
            (x, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            color,
            2,
            cv2.LINE_AA,
        )

        if activity:
            cv2.putText(
                frame,
                activity,
                (x, y + 20),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (200, 200, 200),
                1,
                cv2.LINE_AA,
            )

    def _draw_progress_bar(
        self,
        frame: np.ndarray,
        current_state: ActionState,
        x: int,
        y: int,
    ):
        """Draw 3-step progress bar for the hydration sequence."""
        steps = [
            (ActionState.BOTTLE_IN_HAND, "Lift"),
            (ActionState.CAP_OPENING, "Cap"),
            (ActionState.DRINKING, "Drink"),
        ]

        step_width = 60
        step_height = 20
        gap = 5

        state_order = [ActionState.IDLE, ActionState.BOTTLE_IN_HAND,
                       ActionState.CAP_OPENING, ActionState.DRINKING, ActionState.COMPLETED]
        try:
            current_idx = state_order.index(current_state)
        except ValueError:
            current_idx = 0

        for i, (state, label) in enumerate(steps):
            step_x = x + i * (step_width + gap)
            step_idx = state_order.index(state)

            if current_idx > step_idx:
                color = COLORS["progress_active"]
            elif current_idx == step_idx:
                color = STATE_COLORS.get(state, COLORS["progress_active"])
            else:
                color = COLORS["progress_inactive"]

            cv2.rectangle(
                frame,
                (step_x, y),
                (step_x + step_width, y + step_height),
                color,
                -1 if current_idx >= step_idx else 1,
            )

            text_color = (0, 0, 0) if current_idx >= step_idx else COLORS["text"]
            cv2.putText(
                frame,
                label,
                (step_x + 10, y + 15),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.4,
                text_color,
                1,
                cv2.LINE_AA,
            )

    def _draw_system_status(
        self,
        frame: np.ndarray,
        fps: float,
        latency_ms: int,
        status: str,
    ):
        """Draw system status overlay in corner."""
        h, w = frame.shape[:2]

        status_text = f"FPS: {fps:.1f} | Latency: {latency_ms}ms | {status.upper()}"

        text_size, _ = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
        cv2.rectangle(
            frame,
            (w - text_size[0] - 20, 5),
            (w - 5, 30),
            COLORS["text_bg"],
            -1,
        )

        status_color = (100, 255, 100) if status == "live" else (100, 100, 255)
        cv2.putText(
            frame,
            status_text,
            (w - text_size[0] - 15, 23),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            status_color,
            1,
            cv2.LINE_AA,
        )

    def _draw_event_banner(self, frame: np.ndarray):
        """Draw a full-width banner when a hydration event is completed."""
        h, w = frame.shape[:2]

        banner_h = 70
        y1 = h // 2 - banner_h // 2
        y2 = h // 2 + banner_h // 2

        roi = frame[y1:y2, 0:w]
        green_bg = np.zeros_like(roi)
        green_bg[:] = (0, 140, 0)
        cv2.addWeighted(green_bg, 0.72, roi, 0.28, 0, roi)
        frame[y1:y2, 0:w] = roi

        cv2.line(frame, (0, y1), (w, y1), (0, 200, 0), 2)
        cv2.line(frame, (0, y2), (w, y2), (0, 200, 0), 2)

        text = "HYDRATION DETECTED"
        font = cv2.FONT_HERSHEY_SIMPLEX
        scale = 1.3
        thickness = 2
        text_size, baseline = cv2.getTextSize(text, font, scale, thickness)
        tx = (w - text_size[0]) // 2
        ty = h // 2 + text_size[1] // 2 - 2

        cv2.putText(frame, text, (tx + 2, ty + 2), font, scale,
                    (0, 0, 0), thickness + 2, cv2.LINE_AA)
        cv2.putText(frame, text, (tx, ty), font, scale,
                    (255, 255, 255), thickness, cv2.LINE_AA)

        icon_x = tx - 50
        icon_y = h // 2
        pts = np.array([
            [icon_x, icon_y],
            [icon_x + 12, icon_y + 14],
            [icon_x + 28, icon_y - 14],
        ], np.int32)
        cv2.polylines(frame, [pts], False, (255, 255, 255), 3, cv2.LINE_AA)
