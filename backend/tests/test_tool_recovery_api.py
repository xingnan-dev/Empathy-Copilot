from fastapi.testclient import TestClient

from backend.app.agent.workflow import InvestigationWorkflow
from backend.app.api.app import create_app
from backend.app.api.services.case_application_service import CaseApplicationService
from backend.app.services.tool_recovery import ToolRecoveryService
from backend.tests.fixtures import CASE_ID
from backend.tests.test_tool_recovery import failed_state, request_for


def test_api_recovers_replays_and_queries_with_lost_response() -> None:
    store, failed = failed_state()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    service = CaseApplicationService(workflow, store)
    client = TestClient(create_app(lambda: service))
    request = request_for(failed).model_dump(mode="json")
    url = f"/api/cases/{CASE_ID}/tool-recoveries"
    response = client.post(url, json=request)
    assert response.status_code == 201
    assert response.json()["continuation"] == "SETTLED"
    location = response.headers["location"]
    assert client.get(location).status_code == 200
    assert client.post(url, json=request).json()["replayed"] is True
    assert workflow.tools.execution_counts == {"get_order_history": 1}
    mismatch = client.post(url, json={**request, "reason": "changed"})
    assert mismatch.status_code == 409 and mismatch.json()["code"] == "REQUEST_ID_CONFLICT"
    assert (
        client.post(url, json={**request, "expected_revision": True}).json()["code"]
        == "INVALID_REQUEST"
    )
    assert (
        client.get("/api/cases/absent/tool-recoveries/" + request["request_id"]).status_code == 404
    )


def test_api_pending_replay_is_202_without_execution() -> None:
    store, failed = failed_state()
    workflow = InvestigationWorkflow(checkpoint_store=store)
    request = request_for(failed)
    ToolRecoveryService(workflow).claim(CASE_ID, request)
    client = TestClient(create_app(lambda: CaseApplicationService(workflow, store)))
    url = f"/api/cases/{CASE_ID}/tool-recoveries"
    result = client.post(url, json=request.model_dump(mode="json"))
    assert result.status_code == 202
    assert client.get(result.headers["location"]).status_code == 202
    assert workflow.tools.execution_counts == {}
