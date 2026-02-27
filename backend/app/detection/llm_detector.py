"""LLM action classifier — classifies *what* a person is doing, not *where* they are."""

import base64
import json
import time
from typing import Optional, Dict, Any, Tuple

import cv2
import numpy as np
from openai import AsyncOpenAI

from app.api.schemas import (
    ActionState,
    BoundingBox,
    ActionResult,
    ActionSignals,
    PersonDetection,
)
from app.config import settings


# Short prompts — fewer input tokens = lower time-to-first-token
_SYSTEM = (
    "You are a hydration-action classifier for a factory safety camera. "
    "Classify what the worker is doing. Return valid JSON only."
)

# Used by detect_action() — YOLO already found bboxes, LLM only classifies action
_ACTION_USER = (
    "What hydration action is this factory worker performing?\n"
    "{context}"
    'Return JSON: {{"state":"<state>","confidence":<0.0-1.0>}}\n'
    "States: idle, bottle_in_hand, cap_opening, drinking, completed."
)

# Fallback prompt used when no YOLO detection — full detection
_FULL_USER = (
    "Detect the hydration state in this image.\n"
    'Return JSON: {{"state":"<state>","confidence":<0.0-1.0>,'
    '"person_bbox":[x1,y1,x2,y2]or null,"bottle_bbox":[x1,y1,x2,y2]or null}}\n'
    "States: idle, bottle_in_hand, cap_opening, drinking, completed.\n"
    "Coordinates normalised 0.0-1.0."
)


class VisionLLMDetector:
    """
    Action classifier using OpenAI vision models.

    Two modes:
    - detect_action(): fast path — YOLO already found persons/bottles, LLM
      only classifies the action from a cropped person region.
    - detect(): fallback full-frame detection when YOLO has no result.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = settings.openai_model,
        max_tokens: int = settings.openai_max_tokens,
    ):
        self.api_key = api_key or settings.openai_api_key
        self.model = model
        self.max_tokens = max_tokens
        self.client: Optional[AsyncOpenAI] = None
        self._last_detection_time = 0.0
        self._last_result: Optional[PersonDetection] = None

    async def initialize(self):
        if not self.api_key:
            raise ValueError("OpenAI API key not configured")
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def close(self):
        if self.client:
            await self.client.close()
            self.client = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def detect_action(
        self,
        crop: np.ndarray,
        bottle_detected: bool = False,
    ) -> Tuple[ActionState, float]:
        """
        Classify the hydration action visible in *crop*.

        crop    — BGR image, typically the person region from YOLO (with padding).
        bottle_detected — whether YOLO already found a bottle near this person.

        Returns (ActionState, confidence).
        """
        if not self.client:
            await self.initialize()

        context = (
            "A water bottle is visible near the person. "
            if bottle_detected
            else "No bottle detected near the person. "
        )
        prompt = _ACTION_USER.format(context=context)

        try:
            image_b64 = self._encode_frame(crop)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_b64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=self.max_tokens,
                temperature=0,
                response_format={"type": "json_object"},
            )

            result = self._parse_response(response.choices[0].message.content or "")
            state = self._parse_state(result.get("state") or "idle")
            confidence = float(result.get("confidence", 0.0))

            self._last_detection_time = time.time()
            return state, confidence

        except Exception as e:
            print(f"LLM action error: {e}")
            return ActionState.UNCERTAIN, 0.0

    async def detect(
        self,
        frame: np.ndarray,
        track_id: int = 0,
    ) -> PersonDetection:
        """
        Full-frame fallback — detects both bboxes AND action.
        Used when YOLO has no detections.
        """
        if not self.client:
            await self.initialize()

        try:
            image_b64 = self._encode_frame(frame)
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": _SYSTEM},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": _FULL_USER},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_b64}",
                                    "detail": "low",
                                },
                            },
                        ],
                    },
                ],
                max_tokens=self.max_tokens,
                temperature=0,
                response_format={"type": "json_object"},
            )

            result = self._parse_response(response.choices[0].message.content or "")
            state = self._parse_state(result.get("state") or "idle")
            detection = PersonDetection(
                track_id=track_id,
                person_bbox=self._parse_bbox(result.get("person_bbox")),
                bottle_bbox=self._parse_bbox(result.get("bottle_bbox")),
                action=ActionResult(
                    state=state,
                    confidence=float(result.get("confidence", 0.0)),
                    signals=ActionSignals(),
                ),
            )
            self._last_result = detection
            self._last_detection_time = time.time()
            return detection

        except Exception as e:
            print(f"LLM detect error: {e}")
            return PersonDetection(
                track_id=track_id,
                person_bbox=None,
                bottle_bbox=None,
                action=ActionResult(
                    state=ActionState.UNCERTAIN,
                    confidence=0.0,
                    signals=ActionSignals(),
                ),
            )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def crop_region(
        self,
        frame: np.ndarray,
        bbox: BoundingBox,
        padding: float = 0.25,
    ) -> np.ndarray:
        """
        Crop the person bounding box from *frame* with extra padding.
        Larger context helps the LLM see hand/bottle interactions.
        """
        h, w = frame.shape[:2]
        pw = padding * (bbox.x2 - bbox.x1)
        ph = padding * (bbox.y2 - bbox.y1)

        x1 = max(0, int((bbox.x1 - pw) * w))
        y1 = max(0, int((bbox.y1 - ph) * h))
        x2 = min(w, int((bbox.x2 + pw) * w))
        y2 = min(h, int((bbox.y2 + ph) * h))

        crop = frame[y1:y2, x1:x2]
        # Ensure crop is not empty
        if crop.size == 0:
            return frame
        return crop

    def _encode_frame(self, frame: np.ndarray, max_size: int = 256) -> str:
        """Resize to max_size and encode as base64 JPEG (quality 60)."""
        h, w = frame.shape[:2]
        if max(h, w) > max_size:
            scale = max_size / max(h, w)
            frame = cv2.resize(
                frame, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA
            )
        ok, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 60])
        if not ok:
            raise RuntimeError("Frame encode failed")
        return base64.standard_b64encode(buf.tobytes()).decode("utf-8")

    def _parse_response(self, text: str) -> Dict[str, Any]:
        text = text.strip()
        for fence in ("```json", "```"):
            if fence in text:
                start = text.find(fence) + len(fence)
                end = text.find("```", start)
                if end > start:
                    text = text[start:end].strip()
                    break
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"state": "idle", "confidence": 0.0}

    def _parse_state(self, raw: str) -> ActionState:
        try:
            return ActionState(raw.lower())
        except ValueError:
            return ActionState.IDLE

    def _parse_bbox(self, v) -> Optional[BoundingBox]:
        if v and len(v) == 4:
            return BoundingBox(x1=v[0], y1=v[1], x2=v[2], y2=v[3])
        return None

    def get_last_result(self) -> Optional[PersonDetection]:
        return self._last_result

    def time_since_last_detection(self) -> float:
        if self._last_detection_time == 0:
            return float("inf")
        return time.time() - self._last_detection_time
