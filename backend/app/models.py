from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class SupplierDelayRequest(BaseModel):
    supplier_id: str = Field(min_length=1, examples=["SUP-042"])
    delay_days: int = Field(ge=1, le=90, examples=[14])


class ConversationRequest(BaseModel):
    question: str = Field(
        min_length=3,
        max_length=500,
        examples=["What revenue is at risk if SUP-042 is delayed by 14 days?"],
    )


class DisruptionContext(BaseModel):
    supplier_id: str
    delay_days: int = Field(ge=1, le=90)
    correlation_id: str | None = None


class MitigationOption(BaseModel):
    supplier_id: str
    supplier_name: str | None = None
    part_id: str
    plant_id: str
    lead_time_days: int | None = None
    available_capacity: int | None = None
    cost_band: str | None = None
    approved: bool | None = None
    recommendation_rank: int | None = None
    coverage_percent: int | None = None
    tradeoff: str | None = None


class DraftMitigationRequest(BaseModel):
    disruption_context: DisruptionContext
    selected_mitigation_option: MitigationOption
    owner: str | None = Field(
        default=None,
        description="Ignored by the API. The server derives the owner from the authenticated principal.",
    )


class ApprovalRequest(BaseModel):
    reason: str = Field(
        default="Approved after reviewing governed impact, evidence, and supplier qualification.",
        min_length=10,
        max_length=500,
    )
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=120)


class RevisionRequest(BaseModel):
    reason: str = Field(
        default="Revise the mitigation assumptions and resubmit for approval.",
        min_length=10,
        max_length=500,
    )
    expected_version: int = Field(ge=1)
    idempotency_key: str = Field(min_length=8, max_length=120)


class MitigationAction(BaseModel):
    audit_id: str
    action_id: str
    disruption_id: str
    correlation_id: str
    status: Literal["PENDING_APPROVAL", "APPROVED", "RETURNED_FOR_REVISION"]
    action_type: Literal["SOURCE_FROM_APPROVED_ALTERNATIVE"]
    part_id: str
    plant_id: str
    proposed_supplier_id: str
    owner: str
    owner_id: str
    rationale: str
    created_at: str
    version: int = 1
    policy_decision_id: str
    qualification_checked_at: str
    approved_by: str | None = None
    approved_by_id: str | None = None
    approved_at: str | None = None
    approval_reason: str | None = None
    returned_by: str | None = None
    returned_by_id: str | None = None
    returned_at: str | None = None
    revision_reason: str | None = None


class ErrorResponse(BaseModel):
    error: str
    detail: str
    correlation_id: str | None = None
    evidence_status: Literal["INSUFFICIENT_EVIDENCE"] | None = None


JsonObject = dict[str, Any]
