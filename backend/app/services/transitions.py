"""Single entry point for formal InvestigationState transitions."""

from datetime import UTC, datetime
from typing import Any

from backend.app.domain.agent import (
    AgentAction,
    AgentStatus,
    InvestigationState,
    TransitionEvent,
)
from backend.app.domain.gaps import evaluate_p0_gaps


class InvalidStateTransitionError(ValueError):
    """Raised when a requested lifecycle transition is not legal."""


ALLOWED_TRANSITIONS: dict[AgentStatus, frozenset[AgentStatus]] = {
    AgentStatus.INVESTIGATING: frozenset(
        {
            AgentStatus.INVESTIGATING,
            AgentStatus.WAITING_FOR_USER,
            AgentStatus.WAITING_FOR_HUMAN,
            AgentStatus.ESCALATED,
            AgentStatus.CONCLUDED,
            AgentStatus.TERMINATED,
        }
    ),
    AgentStatus.WAITING_FOR_USER: frozenset(
        {AgentStatus.INVESTIGATING, AgentStatus.WAITING_FOR_HUMAN, AgentStatus.TERMINATED}
    ),
    AgentStatus.WAITING_FOR_HUMAN: frozenset(
        {AgentStatus.INVESTIGATING, AgentStatus.ESCALATED, AgentStatus.TERMINATED}
    ),
    AgentStatus.READY_FOR_ACTION: frozenset(
        {
            AgentStatus.INVESTIGATING,
            AgentStatus.WAITING_FOR_HUMAN,
            AgentStatus.ESCALATED,
            AgentStatus.CONCLUDED,
            AgentStatus.TERMINATED,
        }
    ),
    AgentStatus.ESCALATED: frozenset(),
    AgentStatus.CONCLUDED: frozenset(),
    AgentStatus.TERMINATED: frozenset(),
}


class StateTransitionService:
    """Validate, timestamp, count, revise, and trace every formal transition."""

    def refresh_derived_gaps(self, state: InvestigationState) -> InvestigationState:
        """Refresh deterministic derived data without creating a lifecycle transition."""

        data = state.model_dump()
        data["evidence_gaps"] = evaluate_p0_gaps(state.case_id, state.evidence)
        return InvestigationState.model_validate(data)

    def transition(
        self,
        state: InvestigationState,
        *,
        to_status: AgentStatus,
        action: AgentAction | None,
        reason: str,
        updates: dict[str, Any] | None = None,
    ) -> InvestigationState:
        if to_status not in ALLOWED_TRANSITIONS[state.status]:
            raise InvalidStateTransitionError(
                f"illegal transition: {state.status.value} -> {to_status.value}"
            )
        if state.step_count >= state.max_steps and to_status is not AgentStatus.TERMINATED:
            raise InvalidStateTransitionError("maximum transitions already reached")

        now = datetime.now(UTC)
        revision = state.state_revision + 1
        next_step_count = (
            state.step_count
            if to_status is AgentStatus.TERMINATED and state.step_count >= state.max_steps
            else state.step_count + 1
        )
        stored_action = (
            None
            if to_status in {AgentStatus.ESCALATED, AgentStatus.CONCLUDED, AgentStatus.TERMINATED}
            else action
        )
        event = TransitionEvent(
            from_status=state.status,
            to_status=to_status,
            action=action,
            reason=reason,
            state_revision=revision,
            timestamp=now,
        )
        data = state.model_dump()
        if updates:
            data.update(updates)
        data.update(
            {
                "status": to_status,
                "current_action": stored_action,
                "next_action_reason": reason,
                "step_count": next_step_count,
                "state_revision": revision,
                "updated_at": now,
                "transition_events": [*state.transition_events, event],
            }
        )
        return InvestigationState.model_validate(data)

