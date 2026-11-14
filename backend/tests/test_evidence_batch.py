from datetime import timedelta

import pytest

from backend.app.domain.evidence import Evidence
from backend.app.services.grounding import EvidenceContentConflict, merge_evidence_batch
from backend.tests.fixtures import first_use_evidence


def changed(item: Evidence, **updates: object) -> Evidence:
    return Evidence.model_validate({**item.model_dump(), **updates})


def test_generation_time_only_reuses_original_object() -> None:
    old = first_use_evidence()
    new = changed(old, created_at=old.created_at + timedelta(seconds=1))
    result = merge_evidence_batch([old], [new, new])
    assert len(result) == 1 and result[0] is old


@pytest.mark.parametrize("field", ["value", "observed_at", "source", "metadata"])
def test_business_conflict_rejects_whole_batch(field: str) -> None:
    old = first_use_evidence()
    assert isinstance(old.value, dict)
    changes = {
        "value": {**old.value, "product_name": "different"},
        "observed_at": old.observed_at + timedelta(seconds=1),
        "source": {**old.source.model_dump(), "source_label": "different"},
        "metadata": {"version": "different"},
    }
    original = [old]
    with pytest.raises(EvidenceContentConflict):
        merge_evidence_batch(
            original, [changed(old, id="new"), old, changed(old, **{field: changes[field]})]
        )
    assert original == [old]


def test_internal_batch_conflict_and_json_bool_are_not_silently_merged() -> None:
    old = first_use_evidence()
    with pytest.raises(EvidenceContentConflict):
        merge_evidence_batch([], [old, changed(old, metadata={"x": True})])
    with pytest.raises(EvidenceContentConflict):
        merge_evidence_batch(
            [changed(old, metadata={"x": True})], [changed(old, metadata={"x": 1})]
        )
