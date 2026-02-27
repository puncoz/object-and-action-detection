"""YOLO-based object detector for fast per-frame bounding box detection."""

from typing import List, Optional, Tuple

import numpy as np
from ultralytics import YOLO

from app.api.schemas import (
    ActionResult,
    ActionSignals,
    ActionState,
    BoundingBox,
    DetectedObject,
    PersonDetection,
)

# COCO class indices
_PERSON = 0
_BOTTLE = 39


def _bbox_center(b: BoundingBox) -> Tuple[float, float]:
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


def _is_near_person(
    person: BoundingBox, obj_bbox: BoundingBox, margin: float = 0.20
) -> bool:
    """True if obj_bbox centre falls inside the person bbox expanded by *margin*."""
    pw = person.x2 - person.x1
    ph = person.y2 - person.y1
    cx, cy = _bbox_center(obj_bbox)
    return (
        person.x1 - margin * pw <= cx <= person.x2 + margin * pw
        and person.y1 - margin * ph <= cy <= person.y2 + margin * ph
    )


class YOLODetector:
    """
    Thin wrapper around a YOLO11 model.

    Detects all 80 COCO classes.  Each person's nearby_objects list contains
    every detected object whose centre falls within the person bbox (expanded
    by 20%).  bottle_bbox is kept for backward-compat with MoveNet/LLM.
    Action state is always IDLE here — the LLM loop fills that in separately.

    Returns
    -------
    detect() -> (List[PersonDetection], List[DetectedObject])
        persons (with nearby_objects / bottle_bbox),
        standalone objects not near any person.
    """

    def __init__(self, model_name: str = "yolo11n.pt", confidence: float = 0.35):
        self._model = YOLO(model_name)
        self._confidence = confidence

    def warmup(self, frame_shape: tuple = (720, 1280, 3)) -> None:
        """Run a dummy inference so the first real call isn't slow."""
        dummy = np.zeros(frame_shape, dtype=np.uint8)
        self._model.predict(dummy, conf=self._confidence, verbose=False)

    def detect(
        self, frame: np.ndarray
    ) -> Tuple[List[PersonDetection], List[DetectedObject]]:
        """
        Detect all objects; return persons + standalone objects.

        Uses ByteTrack so track IDs stay consistent across frames.
        """
        h, w = frame.shape[:2]
        names = self._model.names  # {class_id: class_name}

        results = self._model.track(
            frame,
            conf=self._confidence,
            persist=True,   # keeps tracker state between calls
            verbose=False,
        )

        if not results or results[0].boxes is None:
            return [], []

        boxes = results[0].boxes
        persons: List[Tuple[int, BoundingBox]] = []   # (track_id, bbox)
        all_objects: List[DetectedObject] = []

        for i in range(len(boxes)):
            cls = int(boxes.cls[i])
            conf = float(boxes.conf[i])
            x1, y1, x2, y2 = boxes.xyxy[i].tolist()
            bbox = BoundingBox(x1=x1 / w, y1=y1 / h, x2=x2 / w, y2=y2 / h)
            tid = int(boxes.id[i]) if boxes.id is not None else i

            if cls == _PERSON:
                persons.append((tid, bbox))
            else:
                all_objects.append(
                    DetectedObject(
                        class_id=cls,
                        class_name=names.get(cls, str(cls)),
                        bbox=bbox,
                        confidence=conf,
                        track_id=tid,
                    )
                )

        # Associate objects with the nearest person (within expanded bbox)
        assigned_ids: set = set()
        person_detections: List[PersonDetection] = []

        for track_id, person_bbox in persons:
            nearby = [obj for obj in all_objects if _is_near_person(person_bbox, obj.bbox)]
            for obj in nearby:
                assigned_ids.add(id(obj))

            bottle_candidates = [obj.bbox for obj in nearby if obj.class_id == _BOTTLE]
            bottle_bbox = _nearest_bottle(person_bbox, bottle_candidates)

            person_detections.append(
                PersonDetection(
                    track_id=track_id,
                    person_bbox=person_bbox,
                    bottle_bbox=bottle_bbox,
                    nearby_objects=nearby,
                    action=ActionResult(
                        state=ActionState.IDLE,
                        confidence=0.0,
                        signals=ActionSignals(),
                    ),
                )
            )

        # Objects not near any person are "standalone"
        standalone_objects = [obj for obj in all_objects if id(obj) not in assigned_ids]
        return person_detections, standalone_objects
