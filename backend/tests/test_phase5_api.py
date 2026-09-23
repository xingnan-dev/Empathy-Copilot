from fastapi.testclient import TestClient

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.api.app import create_app
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.services.checkpoints import InMemoryCheckpointStore
from backend.tests.fixtures import initial_state


def service_with_s00154() -> tuple[CaseApplicationService, InMemoryCheckpointStore]:
    store = InMemoryCheckpointStore()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    service = CaseApplicationService(workflow, store)
    service.ensure_integration_fixture()
    return service, store


def client_for(service: CaseApplicationService) -> TestClient:
    return TestClient(create_app(lambda: service))


def test_get_case_projection_preserves_evidence_provenance_gaps_and_boundary() -> None:
    service, _ = service_with_s00154()
    response = client_for(service).get("/api/cases/S00154")
    assert response.status_code == 200
    body = response.json()
    assert body["lifecycle"] == "WAITING_FOR_HUMAN"
    assert body["current_action"] == "ESCALATE"
    assert body["attribution_status"] == "INSUFFICIENT_EVIDENCE"
    assert {item["type"] for item in body["evidence"]} >= {
        "VERIFIED_BUSINESS_FACT",
        "CONSUMER_REPORTED",
        "AI_OBSERVATION",
    }
    assert all(item["source"] and item["provenance"] for item in body["evidence"])
    assert {item["id"] for item in body["gaps"]} == {
        "EXACT_PRODUCT_USED",
        "ACTUAL_FIRST_USE_TIME",
        "RECENT_REGIMEN_CHANGES",
        "CURRENT_SYMPTOM_PROGRESSION",
    }
    assert not any(
        item["id"] == "order-purchase" and "used" in item["fact"].lower()
        for item in body["evidence"]
    )


def test_get_unknown_case_has_stable_error_contract() -> None:
    service, _ = service_with_s00154()
    response = client_for(service).get("/api/cases/unknown")
    assert response.status_code == 404
    assert response.json()["code"] == "CASE_NOT_FOUND"


def test_human_approval_transitions_persists_and_reloads() -> None:
    service, store = service_with_s00154()
    client = client_for(service)
    before = client.get("/api/cases/S00154").json()
    approved = client.post(
        "/api/cases/S00154/human-approval",
        json={"expected_revision": before["revision"]},
    )
    assert approved.status_code == 200
    body = approved.json()
    assert body["lifecycle"] == "ESCALATED"
    assert body["human_checkpoint"]["state"] == "APPROVED"
    assert body["revision"] == before["revision"] + 1
    restarted = CaseApplicationService(InvestigationWorkflow(checkpoint_store=store), store)
    assert restarted.get_case("S00154").human_checkpoint.state == "APPROVED"


def test_human_approval_rejects_stale_revision_and_invalid_transition() -> None:
    service, _ = service_with_s00154()
    client = client_for(service)
    assert (
        client.post("/api/cases/S00154/human-approval", json={"expected_revision": 0}).status_code
        == 409
    )
    revision = client.get("/api/cases/S00154").json()["revision"]
    assert (
        client.post(
            "/api/cases/S00154/human-approval", json={"expected_revision": revision}
        ).status_code
        == 200
    )
    current = client.get("/api/cases/S00154").json()["revision"]
    response = client.post("/api/cases/S00154/human-approval", json={"expected_revision": current})
    assert response.status_code == 409
    assert response.json()["code"] == "INVALID_TRANSITION"


def test_resume_success_and_invalid_evidence() -> None:
    store = InMemoryCheckpointStore()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    waiting = workflow.run(initial_state())
    service = CaseApplicationService(workflow, store)
    client = client_for(service)
    response = client.post(
        f"/api/cases/{waiting.case_id}/resume",
        json={
            "expected_revision": waiting.state_revision,
            "gap": "ACTUAL_FIRST_USE_TIME",
            "value": {
                "product_id": "c_serum",
                "product_name": "C Serum",
                "first_use_at": "2026-09-12",
            },
            "source_id": "M-P5",
        },
    )
    assert response.status_code == 200
    invalid = client.post(
        f"/api/cases/{waiting.case_id}/resume",
        json={
            "expected_revision": response.json()["revision"],
            "gap": "SUPPORTED",
            "value": True,
            "source_id": "M-P5",
        },
    )
    assert invalid.status_code == 422
