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


def test_pending_inbox_survives_request_boundaries_and_blocks_duplicates(monkeypatch) -> None:
    isolated = SupplyChainService(FixtureRepository())
    monkeypatch.setattr(main_module, "service", isolated)
    client = TestClient(main_module.app)
    planner_headers = {"X-Demo-Actor": "maya.iyer"}
    approver_headers = {"X-Demo-Actor": "aisha.rao"}

    created = client.post(
        "/api/mitigations/draft",
        headers=planner_headers,
        json=draft_payload(),
    )
    duplicate = client.post(
        "/api/mitigations/draft",
        headers=planner_headers,
        json=draft_payload(),
    )
    inbox = client.get(
        "/api/mitigations?status=PENDING_APPROVAL",
        headers=approver_headers,
    )
    anonymous_inbox = client.get("/api/mitigations?status=PENDING_APPROVAL")

    assert created.status_code == 200
    assert duplicate.status_code == 409
    assert inbox.status_code == 200
    assert inbox.json()["count"] == 1
    assert inbox.json()["mitigations"][0]["action_id"] == created.json()["action_id"]
    assert anonymous_inbox.status_code == 403


def test_scenario_comparison_endpoint_returns_governed_curve(monkeypatch) -> None:
    isolated = SupplyChainService(FixtureRepository())
    monkeypatch.setattr(main_module, "service", isolated)
    client = TestClient(main_module.app)

    response = client.get(
        "/api/scenarios/compare?supplier_id=SUP-042&delay_days=3&delay_days=7&delay_days=14"
    )

    assert response.status_code == 200
    assert [item["revenue_at_risk"] for item in response.json()["scenarios"]] == [
        0,
        436_000,
        586_000,
    ]


def test_spcs_identity_ignores_demo_header_and_enforces_owner_separation(monkeypatch) -> None:
    isolated = SupplyChainService(FixtureRepository())
    monkeypatch.setattr(main_module, "service", isolated)
    monkeypatch.setenv("SUPPLYCHAIN_IDENTITY_MODE", "spcs")
    monkeypatch.setenv("SUPPLYCHAIN_PLANNER_USERS", "PLANNER_USER")
    monkeypatch.setenv("SUPPLYCHAIN_APPROVER_USERS", "PLANNER_USER,APPROVER_USER")
    client = TestClient(main_module.app)

    spoofed = client.post(
        "/api/mitigations/draft",
        headers={"X-Demo-Actor": "maya.iyer"},
        json=draft_payload(),
    )
    session = client.get(
        "/api/session",
        headers={"Sf-Context-Current-User": "planner_user"},
    )
    created = client.post(
        "/api/mitigations/draft",
        headers={"Sf-Context-Current-User": "planner_user"},
        json=draft_payload(),
    )

    assert spoofed.status_code == 401
    assert session.status_code == 200
    assert session.json()["identity_source"] == "SNOWFLAKE_SPCS_INGRESS"
    assert created.status_code == 200
    assert created.json()["owner_id"] == "planner_user"

    decision = {
        "reason": "Independent reviewer verified evidence and qualification.",
        "expected_version": created.json()["version"],
        "idempotency_key": "spcs-independent-v1",
    }
    self_approval = client.post(
        f"/api/mitigations/{created.json()['action_id']}/approve",
        headers={"Sf-Context-Current-User": "planner_user"},
        json=decision,
    )
    independent_approval = client.post(
        f"/api/mitigations/{created.json()['action_id']}/approve",
        headers={"Sf-Context-Current-User": "approver_user"},
        json=decision,
    )

    assert self_approval.status_code == 403
    assert independent_approval.status_code == 200
    assert independent_approval.json()["approved_by_id"] == "approver_user"
