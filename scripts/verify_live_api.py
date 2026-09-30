from __future__ import annotations

import argparse
import json
from uuid import uuid4

import httpx


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Exercise the live governed draft and approval workflow."
    )
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    args = parser.parse_args()

    key = f"live-{uuid4().hex[:16]}"
    with httpx.Client(base_url=args.base_url, timeout=60) as client:
        health = client.get("/health")
        health.raise_for_status()
        assert health.json()["mode"] == "snowflake"

        draft_response = client.post(
            "/api/mitigations/draft",
            headers={"X-Demo-Actor": "maya.iyer"},
            json={
                "disruption_context": {
                    "supplier_id": "SUP-042",
                    "delay_days": 14,
                    "correlation_id": f"WF-LIVE-{key[-8:].upper()}",
                },
                "selected_mitigation_option": {
                    "supplier_id": "SUP-017",
                    "part_id": "PRT-AX14",
                    "plant_id": "PLT-PUN",
                },
            },
        )
        draft_response.raise_for_status()
        draft = draft_response.json()
        assert draft["status"] == "PENDING_APPROVAL"

        decision = {
            "reason": "Live Snowflake verification after governed evidence review.",
            "expected_version": draft["version"],
            "idempotency_key": key,
        }
        self_approval = client.post(
            f"/api/mitigations/{draft['action_id']}/approve",
            headers={"X-Demo-Actor": "maya.iyer"},
            json=decision,
        )
        assert self_approval.status_code == 403

        approved_response = client.post(
            f"/api/mitigations/{draft['action_id']}/approve",
            headers={"X-Demo-Actor": "aisha.rao"},
            json=decision,
        )
        approved_response.raise_for_status()
        approved = approved_response.json()
        assert approved["status"] == "APPROVED"
        assert approved["version"] == 2

        replay_response = client.post(
            f"/api/mitigations/{draft['action_id']}/approve",
            headers={"X-Demo-Actor": "aisha.rao"},
            json=decision,
        )
        replay_response.raise_for_status()
        assert replay_response.json() == approved

        audits_response = client.get("/api/audit-events")
        audits_response.raise_for_status()
        approval_audits = [
            item
            for item in audits_response.json()["audit_events"]
            if item["audit_id"] == approved["audit_id"]
        ]
        assert len(approval_audits) == 1

    print(
        json.dumps(
            {
                "status": "PASS",
                "repository_mode": health.json()["mode"],
                "action_id": approved["action_id"],
                "draft_audit_id": draft["audit_id"],
                "approval_audit_id": approved["audit_id"],
                "self_approval_status": self_approval.status_code,
                "approved_version": approved["version"],
                "idempotent_replay": True,
                "approval_audit_rows": len(approval_audits),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
