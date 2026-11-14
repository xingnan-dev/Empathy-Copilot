"""Recovery-chain invariants, independent of workflow and storage."""

import json
from hashlib import sha256
from typing import TYPE_CHECKING

from pydantic import JsonValue

if TYPE_CHECKING:
    from .agent import InvestigationState, ToolCallRecord


def canonical_arguments(arguments: dict[str, JsonValue]) -> str:
    return json.dumps(arguments, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def logical_call_id(case_id: str, tool_name: str, arguments: dict[str, JsonValue]) -> str:
    payload = f"{case_id}\n{tool_name}\n{canonical_arguments(arguments)}"
    return sha256(payload.encode()).hexdigest()[:32]


def validate_tool_history(state: "InvestigationState") -> None:
    from .agent import ContinuationStatus, ToolCallStatus, ToolFailureKind

    calls = {call.id: call for call in state.tool_calls}
    requests = {record.request_id: record for record in state.tool_recoveries}
    if len(calls) != len(state.tool_calls) or len(requests) != len(state.tool_recoveries):
        raise ValueError("duplicate attempt or recovery identity")
    children: dict[str, str] = {}
    used_requests = set()
    identities: dict[str, tuple[str, str]] = {}
    for call in state.tool_calls:
        key = logical_call_id(state.case_id, call.tool_name, call.arguments)
        identity = (call.tool_name, canonical_arguments(call.arguments))
        if key in identities and identities[key] != identity:
            raise ValueError("logical identity hash collision")
        identities[key] = identity
        if call.invocation_id is not None and call.invocation_id != key:
            raise ValueError("invocation identity disagrees with tool arguments")
        if call.previous_attempt_id is None:
            if call.recovery_request_id is not None or call.attempt_sequence not in {None, 1}:
                raise ValueError("invalid root attempt")
            continue
        parent = calls.get(call.previous_attempt_id)
        record = requests.get(call.recovery_request_id) if call.recovery_request_id else None
        if parent is None or record is None or parent.id == call.id:
            raise ValueError("missing recovery parent or request")
        if logical_call_id(state.case_id, parent.tool_name, parent.arguments) != key:
            raise ValueError("cross-call recovery parent")
        if (parent.tool_name, canonical_arguments(parent.arguments)) != identity:
            raise ValueError("recovery changed arguments")
        if call.attempt_sequence != (parent.attempt_sequence or 1) + 1:
            raise ValueError("invalid attempt sequence")
        if parent.id in children:
            raise ValueError("branching recovery chain")
        children[parent.id] = call.id
        if (
            record.target_attempt_id != parent.id
            or record.new_attempt_id != call.id
            or record.logical_call_id != key
            or record.request_id in used_requests
        ):
            raise ValueError("recovery request disagrees with chain")
        used_requests.add(record.request_id)
        if parent.status is ToolCallStatus.FAILED:
            if parent.failure_kind is not ToolFailureKind.RETRYABLE or record.interrupted_status:
                raise ValueError("failed parent is not recoverable")
        elif parent.status in {ToolCallStatus.PENDING, ToolCallStatus.RUNNING}:
            if record.interrupted_status is not parent.status:
                raise ValueError("interrupted parent status missing")
        else:
            raise ValueError("completed parent cannot be recovered")
        if record.accepted_at < parent.created_at:
            raise ValueError("recovery predates parent")
        if (
            record.continuation is ContinuationStatus.PENDING
            and call.status is not ToolCallStatus.PENDING
        ):
            raise ValueError("pending request has advanced attempt")
        if record.continuation is ContinuationStatus.SETTLED and call.status not in {
            ToolCallStatus.COMPLETED,
            ToolCallStatus.FAILED,
        }:
            raise ValueError("settled request requires finished attempt")
    if used_requests != set(requests):
        raise ValueError("orphan recovery request")
    for record in state.tool_recoveries:
        if (record.new_attempt_id in children) != (
            record.continuation is ContinuationStatus.INTERRUPTED
        ):
            raise ValueError("interrupted request must have a successor")
    # Roots without new recovery structure retain their legacy interpretation; the selector
    # rejects ambiguous duplicate logical roots before execution rather than discarding history.
    for call in state.tool_calls:
        visited = set()
        cursor: ToolCallRecord | None = call
        while cursor is not None:
            if cursor.id in visited:
                raise ValueError("cyclic recovery chain")
            visited.add(cursor.id)
            cursor = calls.get(cursor.previous_attempt_id or "")
