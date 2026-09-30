from fastapi.testclient import TestClient

from app import main as main_module
from app.data import FixtureRepository
from app.service import SupplyChainService


def draft_payload() -> dict:
    return {
        "disruption_context": {
            "supplier_id": "SUP-042",
            "delay_days": 14,
            "correlation_id": "WF-API-GUARD",
        },
        "selected_mitigation_option": {
            "supplier_id": "SUP-017",
            "part_id": "PRT-AX14",
            "plant_id": "PLT-PUN",
        },
    }


def test_api_enforces_planner_and_independent_approver(monkeypatch) -> None:
    isolated = SupplyChainService(FixtureRepository())
    monkeypatch.setattr(main_module, "service", isolated)
    client = TestClient(main_module.app)

    anonymous = client.post("/api/mitigations/draft", json=draft_payload())
    wrong_role = client.post(
        "/api/mitigations/draft",
        headers={"X-Demo-Actor": "aisha.rao"},
        json=draft_payload(),
    )
    created = client.post(
        "/api/mitigations/draft",
        headers={"X-Demo-Actor": "maya.iyer"},
        json=draft_payload(),
    )

    assert anonymous.status_code == 403
    assert wrong_role.status_code == 403
    assert created.status_code == 200
    action = created.json()
    assert action["owner_id"] == "maya.iyer"

    planner_approval = client.post(
        f"/api/mitigations/{action['action_id']}/approve",
        headers={"X-Demo-Actor": "maya.iyer"},
        json={
            "reason": "Planner should not be authorized to approve this action.",
            "expected_version": action["version"],
            "idempotency_key": "planner-approval-v1",
        },
    )
    approver_approval = client.post(
        f"/api/mitigations/{action['action_id']}/approve",
        headers={"X-Demo-Actor": "aisha.rao"},
        json={
            "reason": "Reviewed governed impact, evidence, and qualification.",
            "expected_version": action["version"],
            "idempotency_key": "independent-approval-v1",
        },
    )

    assert planner_approval.status_code == 403
    assert approver_approval.status_code == 200
    assert approver_approval.json()["approved_by_id"] == "aisha.rao"
