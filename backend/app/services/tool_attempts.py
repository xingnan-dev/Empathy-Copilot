"""Shared effective-attempt selection for policy and execution."""

from backend.app.domain.agent import InvestigationState, ToolCallRecord
from backend.app.domain.tool_history import logical_call_id, validate_tool_history


class LegacyAmbiguityError(ValueError):
    pass


def effective_tool_calls(state: InvestigationState) -> dict[str, ToolCallRecord]:
    validate_tool_history(state)
    replaced = {call.previous_attempt_id for call in state.tool_calls if call.previous_attempt_id}
    result: dict[str, ToolCallRecord] = {}
    for call in state.tool_calls:
        if call.id in replaced:
            continue
        key = logical_call_id(state.case_id, call.tool_name, call.arguments)
        if key in result:
            raise LegacyAmbiguityError("ambiguous legacy logical call")
        result[key] = call
    return result
