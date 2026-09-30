import pytest

from app.data import FixtureRepository
from app.models import DisruptionContext, MitigationOption
from app.service import SupplyChainService


def draft(service: SupplyChainService):
    return service.draft_mitigation(
        DisruptionContext(supplier_id="SUP-042", delay_days=14, correlation_id="WF-GUARD"),
        MitigationOption(supplier_id="SUP-017", part_id="PRT-AX14", plant_id="PLT-PUN"),
        "Maya Iyer · Supply Planning",
        "maya.iyer",
    )


def test_owner_cannot_approve_own_draft() -> None:
    service = SupplyChainService(FixtureRepository())
    action = draft(service)

    with pytest.raises(ValueError, match="Separation-of-duties"):
        service.approve_mitigation(
            action.action_id,
            "Maya Iyer · Supply Planning",
            "maya.iyer",
            action.version,
            "Attempted self approval for test.",
            "self-approval-v1",
        )


def test_stale_action_version_is_rejected() -> None:
    service = SupplyChainService(FixtureRepository())
    action = draft(service)

    with pytest.raises(ValueError, match="changed from version"):
        service.approve_mitigation(
            action.action_id,
            "Aisha Rao · VP Operations",
            "aisha.rao",
            99,
            "Reviewed governed evidence and qualification.",
            "stale-action-v99",
        )


def test_qualification_is_revalidated_at_approval_time() -> None:
    repo = FixtureRepository()
    service = SupplyChainService(repo)
    action = draft(service)
    for row in repo._data["supplier_parts"]:
        if row["supplier_id"] == "SUP-017" and row["part_id"] == "PRT-AX14":
            row["approved"] = False

    with pytest.raises(ValueError, match="no longer valid"):
        service.approve_mitigation(
            action.action_id,
            "Aisha Rao · VP Operations",
            "aisha.rao",
            action.version,
            "Reviewed governed evidence and qualification.",
            "revoked-qualification-v1",
        )


def test_approval_is_idempotent_and_versioned() -> None:
    service = SupplyChainService(FixtureRepository())
    action = draft(service)

    first = service.approve_mitigation(
        action.action_id,
        "Aisha Rao · VP Operations",
        "aisha.rao",
        action.version,
        "Reviewed governed evidence and qualification.",
        "approve-once-v1",
    )
    second = service.approve_mitigation(
        action.action_id,
        "Aisha Rao · VP Operations",
        "aisha.rao",
        action.version,
        "Reviewed governed evidence and qualification.",
        "approve-once-v1",
    )

    assert first.status == "APPROVED"
    assert first.version == 2
    assert second.model_dump() == first.model_dump()
    approval_events = [
        event for event in service.repo.audit_events if event["event_type"] == "HUMAN_APPROVAL_RECORDED"
    ]
    assert len(approval_events) == 1
    assert first.audit_id == approval_events[0]["audit_id"]


def test_draft_audit_id_resolves_to_real_event() -> None:
    service = SupplyChainService(FixtureRepository())
    action = draft(service)

    assert any(event["audit_id"] == action.audit_id for event in service.repo.audit_events)
