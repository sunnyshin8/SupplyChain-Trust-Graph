import pytest

from app.data import FixtureRepository
from app.models import DisruptionContext, MitigationOption
from app.service import SupplyChainService


def make_service() -> SupplyChainService:
    return SupplyChainService(FixtureRepository())


def test_unapproved_supplier_cannot_be_recommended_or_drafted() -> None:
    service = make_service()
    alternatives = service.list_approved_alternatives("PRT-AX14", "PLT-PUN")

    assert all(item["approved"] for item in alternatives["approved_alternatives"])
    assert "SUP-031" not in {item["supplier_id"] for item in alternatives["approved_alternatives"]}
    assert alternatives["excluded_unapproved_count"] == 1

    with pytest.raises(ValueError, match="not approved"):
        service.draft_mitigation(
            DisruptionContext(supplier_id="SUP-042", delay_days=14, correlation_id="WF-TEST"),
            MitigationOption(supplier_id="SUP-031", part_id="PRT-AX14", plant_id="PLT-PUN"),
            "Test Planner",
        )


def test_mitigation_stays_pending_until_human_approval() -> None:
    service = make_service()
    action = service.draft_mitigation(
        DisruptionContext(supplier_id="SUP-042", delay_days=14, correlation_id="WF-TEST"),
        MitigationOption(supplier_id="SUP-017", part_id="PRT-AX14", plant_id="PLT-PUN"),
        "Maya Iyer",
    )

    assert action.status == "PENDING_APPROVAL"
    assert action.approved_by is None
    assert len(service.repo.mitigation_actions) == 1
    assert service.repo.audit_events[0]["event_type"] == "MITIGATION_DRAFTED"

    approved = service.approve_mitigation(action.action_id, "Aisha Rao")
    assert approved.status == "APPROVED"
    assert approved.approved_by == "Aisha Rao"
    assert service.repo.audit_events[0]["event_type"] == "HUMAN_APPROVAL_RECORDED"


def test_mitigation_can_be_returned_for_revision_without_execution() -> None:
    service = make_service()
    action = service.draft_mitigation(
        DisruptionContext(supplier_id="SUP-042", delay_days=14, correlation_id="WF-TEST"),
        MitigationOption(supplier_id="SUP-018", part_id="PRT-CTRL9", plant_id="PLT-BLR"),
        "Maya Iyer",
    )

    returned = service.return_mitigation_for_revision(
        action.action_id,
        "Aisha Rao",
        "Confirm the premium freight assumption.",
    )

    assert returned.status == "RETURNED_FOR_REVISION"
    assert returned.returned_by == "Aisha Rao"
    assert returned.revision_reason == "Confirm the premium freight assumption."
    assert service.repo.audit_events[0]["event_type"] == "MITIGATION_RETURNED_FOR_REVISION"
    assert returned.audit_id == service.repo.audit_events[0]["audit_id"]
    assert service.demo_bundle("SUP-042", 14)["summary"]["pending_approvals"] == 0


def test_disrupted_supplier_cannot_be_its_own_alternative() -> None:
    with pytest.raises(ValueError, match="cannot be selected"):
        make_service().draft_mitigation(
            DisruptionContext(supplier_id="SUP-042", delay_days=14),
            MitigationOption(supplier_id="SUP-042", part_id="PRT-AX14", plant_id="PLT-PUN"),
            "Test Planner",
        )


def test_dashboard_hydration_is_read_only_and_does_not_append_audit_events() -> None:
    service = make_service()
    initial_events = list(service.repo.audit_events)

    service.demo_bundle("SUP-042", 14)
    service.demo_bundle("SUP-042", 14)

    assert service.repo.audit_events == initial_events
