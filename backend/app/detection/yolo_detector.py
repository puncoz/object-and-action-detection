"""YOLO-based object detector for fast per-frame bounding box detection."""

from typing import List, Optional

import numpy as np
from ultralytics import YOLO

from app.api.schemas import (
    ActionResult,
    ActionSignals,
    ActionState,
    BoundingBox,
    PersonDetection,
)

# COCO class indices used by yolo11n / yolov8n
_PERSON = 0
_BOTTLE = 39


def _bbox_center(b: BoundingBox):
    return (b.x1 + b.x2) / 2, (b.y1 + b.y2) / 2


def _nearest_bottle(
    person: BoundingBox, bottles: List[BoundingBox]
) -> Optional[BoundingBox]:
    """Return the bottle whose center is closest to the person's center."""
    if not bottles:
        return None
    px, py = _bbox_center(person)
    return min(
        bottles,
        key=lambda b: ((_bbox_center(b)[0] - px) ** 2 + (_bbox_center(b)[1] - py) ** 2),
    )


class YOLODetector:
    """
    Thin wrapper around a YOLO11 model.

    Runs object tracking on every frame to produce fresh bounding boxes
    for persons and bottles.  Action state is always IDLE here — the LLM
    detection loop fills that in separately.
    """

    def __init__(self, model_name: str = "yolo11n.pt", confidence: float = 0.35):
        self._model = YOLO(model_name)
        self._confidence = confidence

    def warmup(self, frame_shape: tuple = (720, 1280, 3)) -> None:
        """Run a dummy inference so the first real call isn't slow."""
        dummy = np.zeros(frame_shape, dtype=np.uint8)
        self._model.predict(
            dummy, conf=self._confidence, classes=[_PERSON, _BOTTLE], verbose=False
        )

    def detect(self, frame: np.ndarray) -> List[PersonDetection]:
        """
        Detect persons and bottles, return one PersonDetection per person.

        Uses ByteTrack so track IDs stay consistent across frames.
        Returns an empty list when nobody is in frame.
        """
        h, w = frame.shape[:2]

        results = self._model.track(
            frame,
            conf=self._confidence,
            classes=[_PERSON, _BOTTLE],
            persist=True,   # keeps tracker state between calls
            verbose=False,
        )

        if not results or results[0].boxes is None:
            return []

        boxes = results[0].boxes
        persons: List[tuple] = []   # (track_id, BoundingBox)
        bottles: List[BoundingBox] = []

        for i in range(len(boxes)):
            cls = int(boxes.cls[i])
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            bbox = BoundingBox(x1=x1 / w, y1=y1 / h, x2=x2 / w, y2=y2 / h)

            if cls == _PERSON:
                tid = int(boxes.id[i]) if boxes.id is not None else i
                persons.append((tid, bbox))
            elif cls == _BOTTLE:
                bottles.append(bbox)

        detections: List[PersonDetection] = []
        for track_id, person_bbox in persons:
            detections.append(
                PersonDetection(
                    track_id=track_id,
                    person_bbox=person_bbox,
                    bottle_bbox=_nearest_bottle(person_bbox, bottles),
                    action=ActionResult(
                        state=ActionState.IDLE,
                        confidence=0.0,
                        signals=ActionSignals(),
                    ),
                )
            )

        return detections
