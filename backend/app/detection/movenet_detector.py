"""MoveNet-based local pose estimator for fast, offline action detection.

Pipeline:
  frame → resize 192×192 → MoveNet Lightning (TFLite int8) → 17 keypoints
  keypoints + YOLO bottle bbox → heuristic action classifier
  → (ActionState, confidence 0-1, ActionSignals)

Runs every frame via asyncio.to_thread (~15-30 ms on CPU).
No network call required — fully local.
"""

from __future__ import annotations

import logging
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

import cv2
import numpy as np

from app.api.schemas import ActionResult, ActionSignals, ActionState, BoundingBox, PersonDetection, PoseKeypoint

logger = logging.getLogger(__name__)

# ── Keypoint indices (MoveNet output order) ──────────────────────────────────
KP_NOSE        = 0
KP_L_EYE       = 1
KP_R_EYE       = 2
KP_L_EAR       = 3
KP_R_EAR       = 4
KP_L_SHOULDER  = 5
KP_R_SHOULDER  = 6
KP_L_ELBOW     = 7
KP_R_ELBOW     = 8
KP_L_WRIST     = 9
KP_R_WRIST     = 10
KP_L_HIP       = 11
KP_R_HIP       = 12
KP_L_KNEE      = 13
KP_R_KNEE      = 14
KP_L_ANKLE     = 15
KP_R_ANKLE     = 16

# ── Model constants ───────────────────────────────────────────────────────────
# TFHub URL (int8 quantized, 192×192, ~3 MB)
_MODEL_URL  = (
    "https://tfhub.dev/google/lite-model/"
    "movenet/singlepose/lightning/tflite/int8/4?lite-format=tflite"
)
_MODEL_DIR  = Path(__file__).parent.parent.parent / "models"
_MODEL_PATH = _MODEL_DIR / "movenet_lightning.tflite"
_INPUT_SIZE = 192          # Lightning: 192×192 px
_KP_CONF    = 0.25         # Min keypoint confidence to treat as visible


# ── Keypoints helper ─────────────────────────────────────────────────────────

@dataclass
class Keypoints:
    """17 MoveNet keypoints; raw shape (17, 3) — [y, x, confidence] normalised 0-1."""

    raw: np.ndarray

    def xy(self, idx: int) -> Tuple[float, float]:
        """Return (x, y) normalised [0-1] for keypoint *idx*."""
        return float(self.raw[idx, 1]), float(self.raw[idx, 0])

    def conf(self, idx: int) -> float:
        return float(self.raw[idx, 2])

    def visible(self, idx: int) -> bool:
        return self.conf(idx) >= _KP_CONF


# ── Detector ─────────────────────────────────────────────────────────────────

class MoveNetDetector:
    """
    Lightweight MoveNet Lightning TFLite wrapper.

    Usage:
        detector = MoveNetDetector()
        ok = detector.load()          # blocking, call via asyncio.to_thread
        kp = detector.infer(frame)    # blocking, call via asyncio.to_thread
        state, conf, signals = detector.classify_action(kp, bottle_bbox)
    """

    def __init__(self) -> None:
        self._interp = None
        self._input_idx: int = 0
        self._output_idx: int = 0

    @property
    def is_loaded(self) -> bool:
        return self._interp is not None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def load(self) -> bool:
        """Download model if missing, load into interpreter, warm up. Blocking."""
        _MODEL_DIR.mkdir(parents=True, exist_ok=True)

        if not _MODEL_PATH.exists():
            logger.info("Downloading MoveNet Lightning model …")
            try:
                urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
                logger.info("Model saved → %s (%.1f MB)", _MODEL_PATH.name,
                            _MODEL_PATH.stat().st_size / 1e6)
            except Exception as exc:
                logger.error("MoveNet download failed: %s", exc)
                return False

        try:
            from ai_edge_litert.interpreter import Interpreter  # type: ignore
            interp = Interpreter(model_path=str(_MODEL_PATH))
            interp.allocate_tensors()
            inp  = interp.get_input_details()
            out  = interp.get_output_details()
            self._input_idx  = inp[0]["index"]
            self._output_idx = out[0]["index"]
            self._interp = interp

            # Warm-up inference (first call allocates internal buffers)
            dummy = np.zeros((1, _INPUT_SIZE, _INPUT_SIZE, 3), dtype=np.uint8)
            interp.set_tensor(self._input_idx, dummy)
            interp.invoke()
            logger.info("MoveNet Lightning ready (%s)", _MODEL_PATH.name)
            return True

        except Exception as exc:
            logger.error("MoveNet load failed: %s", exc)
            self._interp = None
            return False

    # ── Inference ─────────────────────────────────────────────────────────────

    def infer(self, frame: np.ndarray) -> Optional[Keypoints]:
        """
        Run MoveNet on a full BGR frame.
        Returns Keypoints or None if model unavailable / inference fails.
        Blocking — call via asyncio.to_thread.
        """
        if self._interp is None:
            return None
        try:
            img = cv2.resize(frame, (_INPUT_SIZE, _INPUT_SIZE))
            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            inp = np.expand_dims(img_rgb, axis=0).astype(np.uint8)
            self._interp.set_tensor(self._input_idx, inp)
            self._interp.invoke()
            output = self._interp.get_tensor(self._output_idx)  # (1, 1, 17, 3)
            return Keypoints(raw=output[0, 0])
        except Exception as exc:
            logger.warning("MoveNet inference error: %s", exc)
            return None

    # ── Action classification ─────────────────────────────────────────────────

    def classify_action(
        self,
        kp: Optional[Keypoints],
        bottle_bbox: Optional[BoundingBox],
    ) -> Tuple[ActionState, float, ActionSignals, Optional[List[PoseKeypoint]]]:
        """
        Derive hydration action from pose keypoints + YOLO bottle bbox.

        Priority (highest first):
          drinking > cap_opening > bottle_in_hand > idle

        Returns (ActionState, confidence 0-1, ActionSignals, pose_keypoints_or_None).
        """
        if kp is None:
            return ActionState.IDLE, 0.0, ActionSignals(), None

        signals = self._compute_signals(kp, bottle_bbox)
        pose = _to_pose_keypoints(kp)

        # ── drinking: wrist raised to face level, bottle present ──────────────
        if bottle_bbox is not None and signals.mouth_bottle_proximity >= 0.55:
            conf = min(1.0, signals.mouth_bottle_proximity)
            return ActionState.DRINKING, conf, signals, pose

        # ── cap_opening: wrist near bottle top, arm elevated ─────────────────
        if bottle_bbox is not None and signals.wrist_rotation >= 0.50:
            conf = min(1.0, signals.wrist_rotation)
            return ActionState.CAP_OPENING, conf, signals, pose

        # ── bottle_in_hand: wrist close to bottle centre ──────────────────────
        if bottle_bbox is not None and signals.hand_bottle_proximity >= 0.55:
            conf = min(1.0, signals.hand_bottle_proximity)
            return ActionState.BOTTLE_IN_HAND, conf, signals, pose

        return ActionState.IDLE, 0.85, signals, pose

    # ── Signal computation ────────────────────────────────────────────────────

    def _compute_signals(
        self,
        kp: Keypoints,
        bottle: Optional[BoundingBox],
    ) -> ActionSignals:
        signals = ActionSignals()

        # Choose the more confident wrist
        lw_conf = kp.conf(KP_L_WRIST)
        rw_conf = kp.conf(KP_R_WRIST)
        wrist_idx    = KP_L_WRIST    if lw_conf >= rw_conf else KP_R_WRIST
        elbow_idx    = KP_L_ELBOW   if wrist_idx == KP_L_WRIST else KP_R_ELBOW
        shoulder_idx = KP_L_SHOULDER if wrist_idx == KP_L_WRIST else KP_R_SHOULDER

        wrist_visible = kp.visible(wrist_idx)
        wrist_x, wrist_y = kp.xy(wrist_idx)
        nose_x, nose_y   = kp.xy(KP_NOSE)

        if bottle is not None and wrist_visible:
            bc_x = (bottle.x1 + bottle.x2) / 2.0
            bc_y = (bottle.y1 + bottle.y2) / 2.0
            bottle_h = max(bottle.y2 - bottle.y1, 1e-4)

            # ── hand_bottle_proximity ─────────────────────────────────────────
            # Score 1.0 when wrist centre ≤ 0.05 away; 0.0 at ≥ 0.30 away
            dist = _dist(wrist_x, wrist_y, bc_x, bc_y)
            signals.hand_bottle_proximity = max(0.0, 1.0 - dist / 0.30)

            # ── wrist_rotation (cap_opening) ──────────────────────────────────
            # Wrist near upper 30% of bottle + arm elevated above shoulder
            bottle_top_y = bottle.y1 + 0.30 * bottle_h
            near_top     = wrist_y <= bottle_top_y
            arm_elevated = (
                kp.visible(shoulder_idx)
                and wrist_y < kp.xy(shoulder_idx)[1]
            )
            if near_top and arm_elevated:
                cap_dist = abs(wrist_y - bottle.y1)
                max_dist = 0.30 * bottle_h + 1e-6
                signals.wrist_rotation = max(0.0, 1.0 - cap_dist / max_dist)

            # ── mouth_bottle_proximity (drinking) ─────────────────────────────
            # Wrist raised to nose height (y decreases upward in image coords)
            if kp.visible(KP_NOSE):
                # wrist_y <= nose_y + tolerance means wrist is at/above face
                wrist_at_face = wrist_y <= nose_y + 0.05
                if wrist_at_face:
                    face_dist = abs(wrist_y - nose_y)
                    # Full score when wrist is exactly at nose level
                    signals.mouth_bottle_proximity = max(0.0, 1.0 - face_dist / 0.12)

        # ── neck_hand_proximity ───────────────────────────────────────────────
        if wrist_visible and kp.visible(KP_NOSE):
            dist = _dist(wrist_x, wrist_y, nose_x, nose_y)
            signals.neck_hand_proximity = max(0.0, 1.0 - dist / 0.25)

        return signals


# ── Utilities ─────────────────────────────────────────────────────────────────

def _dist(x1: float, y1: float, x2: float, y2: float) -> float:
    return ((x1 - x2) ** 2 + (y1 - y2) ** 2) ** 0.5


def _to_pose_keypoints(kp: Keypoints) -> List[PoseKeypoint]:
    """Convert raw Keypoints to a list of PoseKeypoint schema objects."""
    return [
        PoseKeypoint(
            x=float(kp.raw[i, 1]),   # MoveNet raw: [y, x, conf]
            y=float(kp.raw[i, 0]),
            conf=float(kp.raw[i, 2]),
        )
        for i in range(17)
    ]
