"""State machine for tracking hydration action sequences."""

import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any

from app.api.schemas import ActionState
from app.config import settings


@dataclass
class StateTransition:
    """Record of a state transition."""
    from_state: ActionState
    to_state: ActionState
    timestamp: datetime
    confidence: float


@dataclass
class TrackedPerson:
    """State tracking for a single person."""
    track_id: int
    current_state: ActionState = ActionState.IDLE
    state_confidence: float = 0.0
    consecutive_frames: int = 0
    state_history: List[StateTransition] = field(default_factory=list)
    sequence_started_at: Optional[datetime] = None
    last_update: datetime = field(default_factory=datetime.utcnow)

    # Accumulated states for current sequence
    sequence_states: List[ActionState] = field(default_factory=list)


class ActionStateMachine:
    """
    State machine for tracking hydration action sequences.

    Valid sequence: IDLE -> BOTTLE_IN_HAND -> CAP_OPENING -> DRINKING -> COMPLETED -> IDLE
    """

    # Valid state transitions
    VALID_TRANSITIONS = {
        ActionState.IDLE: [ActionState.BOTTLE_IN_HAND, ActionState.IDLE],
        ActionState.BOTTLE_IN_HAND: [ActionState.CAP_OPENING, ActionState.IDLE, ActionState.BOTTLE_IN_HAND],
        ActionState.CAP_OPENING: [ActionState.DRINKING, ActionState.BOTTLE_IN_HAND, ActionState.IDLE, ActionState.CAP_OPENING],
        ActionState.DRINKING: [ActionState.COMPLETED, ActionState.IDLE, ActionState.DRINKING],
        ActionState.COMPLETED: [ActionState.IDLE, ActionState.COMPLETED],
        ActionState.UNCERTAIN: [ActionState.IDLE, ActionState.BOTTLE_IN_HAND, ActionState.CAP_OPENING, ActionState.DRINKING],
    }

    # Sequence states that contribute to a completed event
    SEQUENCE_STATES = [ActionState.BOTTLE_IN_HAND,
                       ActionState.CAP_OPENING, ActionState.DRINKING]

    def __init__(
        self,
        confidence_threshold: float = settings.confidence_threshold,
        consecutive_frames_required: int = settings.consecutive_frames_required,
    ):
        self.confidence_threshold = confidence_threshold
        self.consecutive_frames_required = consecutive_frames_required
        self.tracked_persons: Dict[int, TrackedPerson] = {}

    def get_or_create_person(self, track_id: int) -> TrackedPerson:
        """Get or create tracking state for a person."""
        if track_id not in self.tracked_persons:
            self.tracked_persons[track_id] = TrackedPerson(track_id=track_id)
        return self.tracked_persons[track_id]

    def update(
        self,
        track_id: int,
        detected_state: ActionState,
        confidence: float,
    ) -> tuple[ActionState, bool, Optional[Dict[str, Any]]]:
        """
        Update state for a tracked person.

        Returns:
            - current_state: The actual current state after update
            - is_completed: True if sequence just completed
            - event_data: Event data if completed, None otherwise
        """
        person = self.get_or_create_person(track_id)
        now = datetime.utcnow()
        person.last_update = now

        # Handle uncertain state - don't change current state
        if detected_state == ActionState.UNCERTAIN:
            return person.current_state, False, None

        # Check if this is the same state being detected
        if detected_state == person.current_state:
            person.consecutive_frames += 1
            person.state_confidence = max(person.state_confidence, confidence)
            return person.current_state, False, None

        # Check if transition is valid
        if detected_state not in self.VALID_TRANSITIONS.get(person.current_state, []):
            # Invalid transition - reset to idle if stuck
            if confidence > 0.9 and detected_state == ActionState.IDLE:
                return self._reset_to_idle(person), False, None
            return person.current_state, False, None

        # Check confidence threshold
        if confidence < self.confidence_threshold:
            person.consecutive_frames = 0
            return person.current_state, False, None

        # Increment consecutive frames for new state
        person.consecutive_frames += 1

        # Check if we have enough consecutive frames
        if person.consecutive_frames < self.consecutive_frames_required:
            return person.current_state, False, None

        # Perform state transition
        old_state = person.current_state
        person.current_state = detected_state
        person.state_confidence = confidence
        person.consecutive_frames = 1

        # Record transition
        transition = StateTransition(
            from_state=old_state,
            to_state=detected_state,
            timestamp=now,
            confidence=confidence,
        )
        person.state_history.append(transition)

        # Track sequence progress
        if detected_state == ActionState.BOTTLE_IN_HAND and old_state == ActionState.IDLE:
            # Starting a new sequence
            person.sequence_started_at = now
            person.sequence_states = [detected_state]
        elif detected_state in self.SEQUENCE_STATES and person.sequence_started_at:
            if detected_state not in person.sequence_states:
                person.sequence_states.append(detected_state)

        # Check for completion
        if detected_state == ActionState.COMPLETED:
            event_data = self._create_event_data(person)
            self._reset_to_idle(person)
            return ActionState.COMPLETED, True, event_data

        # Reset if going back to idle
        if detected_state == ActionState.IDLE:
            self._reset_to_idle(person)

        return person.current_state, False, None

    def _reset_to_idle(self, person: TrackedPerson) -> ActionState:
        """Reset person state to idle."""
        person.current_state = ActionState.IDLE
        person.state_confidence = 0.0
        person.consecutive_frames = 0
        person.sequence_started_at = None
        person.sequence_states = []
        return ActionState.IDLE

    def _create_event_data(self, person: TrackedPerson) -> Dict[str, Any]:
        """Create event data for a completed sequence."""
        # Calculate average confidence from recent transitions
        recent_transitions = person.state_history[-5:
                                                  ] if person.state_history else []
        avg_confidence = (
            sum(t.confidence for t in recent_transitions) /
            len(recent_transitions)
            if recent_transitions
            else 0.0
        )

        return {
            "track_id": person.track_id,
            "start_ts": person.sequence_started_at,
            "end_ts": datetime.utcnow(),
            "sequence": [s.value for s in person.sequence_states],
            "confidence": avg_confidence,
        }

    def get_person_state(self, track_id: int) -> tuple[ActionState, float]:
        """Get current state and confidence for a person."""
        person = self.tracked_persons.get(track_id)
        if person:
            return person.current_state, person.state_confidence
        return ActionState.IDLE, 0.0

    def get_sequence_progress(self, track_id: int) -> List[ActionState]:
        """Get the current sequence progress for a person."""
        person = self.tracked_persons.get(track_id)
        if person:
            return person.sequence_states.copy()
        return []

    def cleanup_stale(self, max_age_seconds: float = 30.0):
        """Remove tracking for persons not seen recently."""
        now = datetime.utcnow()
        stale_ids = []
        for track_id, person in self.tracked_persons.items():
            age = (now - person.last_update).total_seconds()
            if age > max_age_seconds:
                stale_ids.append(track_id)
        for track_id in stale_ids:
            del self.tracked_persons[track_id]
