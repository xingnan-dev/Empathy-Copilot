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
