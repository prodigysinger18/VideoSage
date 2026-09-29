"""每个人物的行为状态维护。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class BehaviorState:
    """单个人物当前行为状态。"""

    person_id: int
    current_action: str = "standing"
    candidate_action: str = "standing"
    action_start_time: float = 0.0
    last_update_time: float = 0.0
    last_confidence: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "person_id": self.person_id,
            "current_action": self.current_action,
            "candidate_action": self.candidate_action,
            "action_start_time": round(self.action_start_time, 4),
            "last_update_time": round(self.last_update_time, 4),
            "last_confidence": round(self.last_confidence, 4),
        }


class BehaviorStateManager:
    """按 person_id 独立维护行为状态。"""

    def __init__(self) -> None:
        self._states: Dict[int, BehaviorState] = {}

    def update(
        self,
        person_id: int,
        timestamp: float,
        action: str,
        confidence: float,
    ) -> BehaviorState:
        state = self._states.get(person_id)
        if state is None:
            state = BehaviorState(
                person_id=person_id,
                current_action=action,
                candidate_action=action,
                action_start_time=timestamp,
                last_update_time=timestamp,
                last_confidence=confidence,
            )
            self._states[person_id] = state
            return state

        state.candidate_action = action
        state.last_update_time = timestamp
        state.last_confidence = confidence

        if action != state.current_action:
            state.current_action = action
            state.action_start_time = timestamp

        return state

    def get(self, person_id: int) -> Optional[BehaviorState]:
        return self._states.get(person_id)

    def snapshot(self) -> List[Dict[str, Any]]:
        return [state.to_dict() for state in self._states.values()]
