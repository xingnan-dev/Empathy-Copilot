"""Atomic inbound-message boundary; ordinary workflow persistence remains unchanged."""

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.domain.agent import AgentStatus, InvestigationState
from backend.app.domain.inbound_message import InboundMessage
from backend.app.persistence.checkpoints import (
    PostgresCheckpointStore,
    TransactionBoundCheckpointStore,
)
from backend.app.persistence.models import (
    CaseInboundMessageRow,
    InvestigationCheckpointRow,
    MessageRow,
)
from backend.app.services.checkpoints import InMemoryCheckpointStore, StateConflictError
from backend.app.services.message_errors import MessageError
from backend.app.services.transitions import InvalidStateTransitionError

from ..schemas.cases import CaseView, MessageHistoryView, MessageReceipt, MessageView

if TYPE_CHECKING:
    from .case_application_service import CaseApplicationService


class MessagePersistence:
    def __init__(self, service: "CaseApplicationService") -> None:
        self.service = service

    def records(self, case_id: str, session: Session | None = None) -> list[InboundMessage]:
        store = self.service.checkpoints
        if session is not None:
            return [
                InboundMessage.model_validate(row)
                for row in session.scalars(
                    select(CaseInboundMessageRow)
                    .where(CaseInboundMessageRow.case_id == case_id)
                    .order_by(CaseInboundMessageRow.sequence)
                )
            ]
        if isinstance(store, PostgresCheckpointStore):
            with store.session_factory() as own:
                return self.records(case_id, own)
        if isinstance(store, InMemoryCheckpointStore):
            return sorted(
                (m for (cid, _), m in store.message_records.items() if cid == case_id),
                key=lambda m: m.sequence,
            )
        return []

    def view(self, state: InvestigationState, session: Session | None = None) -> CaseView:
        store = self.service.checkpoints
        if session is None and isinstance(store, PostgresCheckpointStore):
            with store.session_factory() as own:
                return self.view(state, own)
        view = self.service._project_state(state)
        history: list[MessageView] = []
        if view.official_data:
            cutoff = self.service._official_message_sequence_cutoff(state)
            if session is not None and cutoff is not None:
                rows = session.scalars(
                    select(MessageRow)
                    .where(MessageRow.session_id == state.case_id, MessageRow.sequence <= cutoff)
                    .order_by(MessageRow.sequence, MessageRow.message_id)
                ).all()
                for row in rows:
                    role = (
                        "CONSUMER"
                        if row.role == "买家"
                        else "AGENT"
                        if row.role == "客服"
                        else "UNKNOWN"
                    )
                    history.append(
                        MessageView(
                            id=row.message_id,
                            case_id=state.case_id,
                            role=role,
                            text=row.text,
                            sent_at=row.sent_at,
                            sequence=row.sequence,
                            origin="OFFICIAL",
                            content_type="TEXT"
                            if row.content_type == "文本"
                            else "IMAGE"
                            if row.content_type == "图片"
                            else "UNKNOWN",
                        )
                    )
                view.message_history = MessageHistoryView(
                    historical_source="OFFICIAL",
                    historical_complete=bool(rows) and len({r.sequence for r in rows}) == len(rows),
                )
        else:
            demo = json.loads(
                (Path(__file__).parents[1] / "demo_messages.json").read_text(encoding="utf-8")
            )
            if not view.official_data and (rows := demo.get(state.case_id)):
                history = [
                    MessageView(
                        **item, case_id=state.case_id, sequence=i + 1, origin="DEMO_FIXTURE"
                    )
                    for i, item in enumerate(rows)
                ]
                view.message_history = MessageHistoryView(
                    historical_source="DEMO_FIXTURE", historical_complete=True
                )
        for message in history:
            message.evidence_ids = [
                e.id
                for e in state.evidence
                if e.case_id == state.case_id and e.source.source_id == message.id
            ]
        live = [
            MessageView(
                id=m.message_id,
                case_id=m.case_id,
                role=m.role,
                text=m.text,
                received_at=m.received_at,
                sequence=m.sequence,
                origin="LIVE",
                content_type="TEXT",
                evidence_ids=m.evidence_ids,
            )
            for m in self.records(state.case_id, session)
        ]
        view.messages = [*history, *live]
        return view

    def get(self, case_id: str) -> CaseView:
        store = self.service.checkpoints
        if isinstance(store, PostgresCheckpointStore):
            try:
                with store.session_factory() as session:
                    session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
                    return self.view(
                        TransactionBoundCheckpointStore(session).load(case_id), session
                    )
            except SQLAlchemyError as error:
                raise MessageError(
                    "MESSAGE_PERSISTENCE_UNAVAILABLE", "Message storage unavailable."
                ) from error
        return self.view(store.load(case_id))

    @staticmethod
    def replay(record: InboundMessage, message: str, revision: int) -> None:
        if record.text != message or record.request_revision != revision:
            raise MessageError(
                "MESSAGE_ID_CONFLICT", "Message identity was used for different content.", 409
            )

    @staticmethod
    def receipt(view: CaseView, record: InboundMessage, replayed: bool) -> CaseView:
        view.message_receipt = MessageReceipt(
            message_id=record.message_id,
            sequence=record.sequence,
            received_at=record.received_at,
            accepted_revision=record.accepted_revision,
            evidence_ids=record.evidence_ids,
            replayed=replayed,
        )
        view.model_dump_json()
        return view

    def ingest(self, case_id: str, message: str, message_id: str, revision: int) -> CaseView:
        store = self.service.checkpoints
        try:
            prior = next((m for m in self.records(case_id) if m.message_id == message_id), None)
            if prior:
                self.replay(prior, message, revision)
                return self.receipt(self.get(case_id), prior, True)
            current = store.load(case_id)
            self.check(current, message_id, revision)
            if self.service.model_service is None:
                from backend.app.llm.provider import ModelProviderError

                raise ModelProviderError("UNAVAILABLE", "model provider is not configured")
            candidates, intent, emotion = self.service.model_service.understand(
                case_id=case_id,
                message_id=message_id,
                message=message,
                observed_at=datetime.now(UTC),
                context={
                    "open_gaps": [g.id for g in self.service._presentation_gaps(current)],
                    "reference_date": datetime.now(UTC).date().isoformat(),
                },
            )
            if isinstance(store, PostgresCheckpointStore):
                committing = False
                try:
                    with store.session_factory() as session, session.begin():
                        session.execute(text("SET LOCAL lock_timeout = '5s'"))
                        session.execute(text("SET LOCAL statement_timeout = '30s'"))
                        session.execute(
                            select(InvestigationCheckpointRow)
                            .where(InvestigationCheckpointRow.case_id == case_id)
                            .with_for_update()
                        )
                        bound = TransactionBoundCheckpointStore(session)
                        current = bound.load(case_id)
                        rows = self.records(case_id, session)
                        prior = next((m for m in rows if m.message_id == message_id), None)
                        if prior:
                            self.replay(prior, message, revision)
                            return self.receipt(self.view(current, session), prior, True)
                        self.check(current, message_id, revision, session)
                        now = datetime.now(UTC)
                        evidence = [e.model_copy(update={"observed_at": now}) for e in candidates]
                        workflow = InvestigationWorkflow(
                            checkpoint_store=bound, tool_registry=self.service.workflow.tools
                        )
                        result = self.service._apply_message(current, evidence, workflow, now)
                        if not evidence:
                            bound.save(result, expected_revision=current.state_revision)
                        record = InboundMessage(
                            case_id=case_id,
                            message_id=message_id,
                            consumer_id=current.consumer_id,
                            text=message,
                            received_at=now,
                            sequence=(rows[-1].sequence + 1 if rows else 1),
                            request_revision=revision,
                            accepted_revision=result.state_revision,
                            evidence_ids=[e.id for e in evidence],
                        )
                        self.validate_links(result, record)
                        session.add(CaseInboundMessageRow(**record.model_dump()))
                        session.flush()
                        view = self.receipt(self.view(result, session), record, False)
                        view.context_passport["model_signals"] = {
                            "intent": intent,
                            "emotion": emotion,
                        }
                        committing = True
                    return view
                except SQLAlchemyError as error:
                    code = (
                        "MESSAGE_COMMIT_UNCERTAIN"
                        if committing
                        else "MESSAGE_PERSISTENCE_UNAVAILABLE"
                    )
                    raise MessageError(
                        code,
                        "Message receipt unconfirmed; query or replay the original request."
                        if committing
                        else "Message not accepted: storage unavailable.",
                    ) from error
            if not isinstance(store, InMemoryCheckpointStore):
                raise MessageError(
                    "MESSAGE_PERSISTENCE_UNAVAILABLE", "Message storage unavailable."
                )
            with store.message_lock:
                prior = store.message_records.get((case_id, message_id))
                if prior:
                    self.replay(prior, message, revision)
                    return self.receipt(self.view(store.load(case_id)), prior, True)
                current = store.load(case_id)
                self.check(current, message_id, revision)
                scratch = InMemoryCheckpointStore()
                scratch.save(current)
                now = datetime.now(UTC)
                evidence = [e.model_copy(update={"observed_at": now}) for e in candidates]
                result = self.service._apply_message(
                    current,
                    evidence,
                    InvestigationWorkflow(
                        checkpoint_store=scratch, tool_registry=self.service.workflow.tools
                    ),
                    now,
                )
                rows = self.records(case_id)
                record = InboundMessage(
                    case_id=case_id,
                    message_id=message_id,
                    consumer_id=current.consumer_id,
                    text=message,
                    received_at=now,
                    sequence=rows[-1].sequence + 1 if rows else 1,
                    request_revision=revision,
                    accepted_revision=result.state_revision,
                    evidence_ids=[e.id for e in evidence],
                )
                self.validate_links(result, record)
                view = self.view(result)
                view.messages.append(
                    MessageView(
                        id=message_id,
                        case_id=case_id,
                        role="CONSUMER",
                        text=message,
                        received_at=now,
                        sequence=record.sequence,
                        origin="LIVE",
                        content_type="TEXT",
                        evidence_ids=record.evidence_ids,
                    )
                )
                view = self.receipt(view, record, False)
                view.context_passport["model_signals"] = {"intent": intent, "emotion": emotion}
                store.save(result, expected_revision=revision)
                store.message_records[(case_id, message_id)] = record
                return view
        except SQLAlchemyError as error:
            raise MessageError(
                "MESSAGE_PERSISTENCE_UNAVAILABLE", "Message storage unavailable."
            ) from error

    def check(
        self,
        state: InvestigationState,
        message_id: str,
        revision: int,
        session: Session | None = None,
    ) -> None:
        if session is None and isinstance(self.service.checkpoints, PostgresCheckpointStore):
            with self.service.checkpoints.session_factory() as own:
                return self.check(state, message_id, revision, own)
        if state.state_revision != revision:
            raise StateConflictError(
                "Case changed; message was not accepted. Refresh before retrying."
            )
        if state.status not in {
            AgentStatus.INVESTIGATING,
            AgentStatus.WAITING_FOR_USER,
            AgentStatus.WAITING_FOR_HUMAN,
        }:
            raise InvalidStateTransitionError("case cannot accept a new message")
        if any(
            m.id == message_id for m in self.view(state, session).messages if m.origin != "LIVE"
        ) or any(e.source.source_id == message_id for e in state.evidence):
            raise MessageError(
                "MESSAGE_ID_CONFLICT", "Message identity collides with existing history.", 409
            )

    @staticmethod
    def validate_links(state: InvestigationState, record: InboundMessage) -> None:
        for evidence_id in record.evidence_ids:
            if not any(
                e.id == evidence_id
                and e.case_id == record.case_id
                and e.source.source_id == record.message_id
                for e in state.evidence
            ):
                raise ValueError("message evidence reference mismatch")
