import pytest

from backend.app.llm.providers.fake import FakeModelProvider
from backend.app.services.message_errors import MessageError
from backend.tests.test_phase6_llm import service_with_provider


def test_no_evidence_message_is_accepted_once_and_preserves_counters() -> None:
    service, _ = service_with_provider(FakeModelProvider())
    before = service.checkpoints.load("S00154")
    first = service.ingest_message(
        "S00154", message="  未知内容  ", message_id="one", expected_revision=before.state_revision
    )
    after = service.checkpoints.load("S00154")
    assert first.messages[-1].text == "  未知内容  "
    assert first.message_receipt is not None
    assert first.message_receipt.evidence_ids == []
    assert after.state_revision == before.state_revision + 1
    assert (
        after.step_count,
        after.question_count,
        after.transition_events,
        after.human_review_blocks,
    ) == (
        before.step_count,
        before.question_count,
        before.transition_events,
        before.human_review_blocks,
    )
    second = service.ingest_message(
        "S00154", message="  未知内容  ", message_id="one", expected_revision=before.state_revision
    )
    assert second.message_receipt is not None
    assert second.message_receipt.replayed
    assert service.model_service is not None
    assert len(service.model_service.calls) == 1
    with pytest.raises(MessageError):
        service.ingest_message(
            "S00154", message="other", message_id="one", expected_revision=before.state_revision
        )


@pytest.mark.parametrize(
    "payload",
    [
        {"message": "   ", "message_id": "id", "expected_revision": 1},
        {"message": "ok", "message_id": "bad id", "expected_revision": 1},
        {"message": "ok", "message_id": "bad\u0080", "expected_revision": 1},
        {"message": "ok", "message_id": "x" * 129, "expected_revision": 1},
        {"message": "ok", "message_id": "id", "expected_revision": 1, "role": "AGENT"},
    ],
)
def test_message_api_validation_is_explicit(payload: dict[str, object]) -> None:
    from fastapi.testclient import TestClient

    from backend.app.api.app import create_app

    service, _ = service_with_provider(FakeModelProvider())
    client = TestClient(create_app(lambda: service))
    result = client.post("/api/cases/S00154/messages", json=payload)
    assert result.status_code == 422
    assert result.json()["code"] == "VALIDATION_ERROR"
    assert service.model_service is not None and service.model_service.calls == []


def test_history_text_is_not_invented_from_evidence() -> None:
    from backend.app.agent.workflow import InvestigationWorkflow
    from backend.app.api.services.case_application_service import CaseApplicationService
    from backend.app.services.checkpoints import InMemoryCheckpointStore
    from backend.tests.fixtures import initial_state

    store = InMemoryCheckpointStore()
    state = initial_state()
    store.save(state)
    view = CaseApplicationService(InvestigationWorkflow(checkpoint_store=store), store).get_case(
        state.case_id
    )
    assert view.messages == []
    assert view.message_history.historical_source == "UNAVAILABLE"


def test_old_fixture_with_accepted_message_is_not_rebuilt_on_restart() -> None:
    from backend.app.agent.workflow import InvestigationWorkflow
    from backend.app.api.fixtures import s00154_waiting_for_human
    from backend.app.api.services.case_application_service import CaseApplicationService
    from backend.app.domain.agent import InvestigationState
    from backend.app.domain.gaps import evaluate_p0_gaps
    from backend.app.llm.service import ModelService
    from backend.app.services.checkpoints import InMemoryCheckpointStore

    store = InMemoryCheckpointStore()
    fixture = s00154_waiting_for_human()
    evidence = [
        e
        for e in fixture.evidence
        if e.id in CaseApplicationService._LEGACY_INTEGRATION_EVIDENCE_IDS
    ]
    data = fixture.model_dump()
    data.update(evidence=evidence, evidence_gaps=evaluate_p0_gaps(fixture.case_id, evidence))
    legacy = InvestigationState.model_validate(data)
    store.save(legacy)
    assert CaseApplicationService._is_legacy_integration_fixture(legacy)
    service = CaseApplicationService(
        InvestigationWorkflow(checkpoint_store=store), store, ModelService(FakeModelProvider())
    )
    result = service.ingest_message(
        fixture.case_id,
        message="keep legacy text",
        message_id="legacy-live",
        expected_revision=legacy.state_revision,
    )
    restarted = CaseApplicationService(InvestigationWorkflow(checkpoint_store=store), store)
    restarted.ensure_integration_fixture()
    assert restarted.get_case(fixture.case_id).revision == result.revision
    assert restarted.get_case(fixture.case_id).messages[-1].text == "keep legacy text"
