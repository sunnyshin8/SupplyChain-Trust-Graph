from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .models import (
    ApprovalRequest,
    ConversationRequest,
    DraftMitigationRequest,
    RevisionRequest,
    SupplierDelayRequest,
)
from .policy import require_any_role, require_role, resolve_identity
from .service import (
    EvidenceError,
    GovernanceAuthorizationError,
    GovernanceConflictError,
    service,
)


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    yield
    service.repo.close()


app = FastAPI(
    title="Supply Chain Management MCP Server",
    version="0.1.0",
    description=(
        "Governed supply-chain disruption intelligence. Analysis is read-only by default; "
        "mitigation changes require explicit human approval."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Correlation-ID", "X-Demo-Actor"],
)


@app.exception_handler(EvidenceError)
async def insufficient_evidence_handler(_: Request, exc: EvidenceError) -> JSONResponse:
    return JSONResponse(
        status_code=404,
        content={
            "error": "insufficient_evidence",
            "detail": str(exc),
            "evidence_status": "INSUFFICIENT_EVIDENCE",
        },
    )


@app.exception_handler(ValueError)
async def validation_handler(_: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(status_code=422, content={"error": "governance_validation_failed", "detail": str(exc)})


@app.exception_handler(GovernanceConflictError)
async def conflict_handler(_: Request, exc: GovernanceConflictError) -> JSONResponse:
    return JSONResponse(status_code=409, content={"error": "workflow_conflict", "detail": str(exc)})


@app.exception_handler(GovernanceAuthorizationError)
async def governance_authorization_handler(
    _: Request,
    exc: GovernanceAuthorizationError,
) -> JSONResponse:
    return JSONResponse(status_code=403, content={"error": "governance_forbidden", "detail": str(exc)})


@app.get("/health", tags=["system"])
def health() -> dict:
    return {
        "status": "ok",
        "service": "Supply Chain Management MCP Server",
        "dependency": service.repo.health_check(),
        **service.repo.status(),
    }


@app.get("/api/session", tags=["governance"])
def current_session(request: Request) -> dict:
    return resolve_identity(request).public()


@app.get("/api/demo", tags=["demo"])
def demo_bundle(
    supplier_id: str = Query(default="SUP-042"),
    delay_days: int = Query(default=14, ge=1, le=90),
) -> dict:
    return service.demo_bundle(supplier_id, delay_days)


@app.get("/api/dashboard", tags=["analytics"])
def dashboard(
    supplier_id: str = Query(default="SUP-042"),
    delay_days: int = Query(default=14, ge=1, le=90),
) -> dict:
    return service.demo_bundle(supplier_id, delay_days)["summary"]


@app.get("/api/scenarios/compare", tags=["analytics"])
def compare_delay_scenarios(
    supplier_id: str = Query(default="SUP-042"),
    delay_days: list[int] = Query(default=[3, 7, 14, 21]),
) -> dict:
    return service.compare_delay_scenarios(supplier_id, delay_days)


@app.get("/api/governed-metrics", tags=["analytics"])
def governed_metrics() -> dict:
    return service.governed_metrics()


@app.post("/api/workflows/supplier-delay", tags=["workflows"])
def analyze_supplier_delay(payload: SupplierDelayRequest, request: Request) -> dict:
    identity = resolve_identity(request)
    return service.analyze_supplier_delay(
        payload.supplier_id,
        payload.delay_days,
        actor=f"{identity.display_name} · {identity.title}",
    )


@app.post("/api/conversation", tags=["conversational analytics"])
def ask_supply_chain(payload: ConversationRequest, request: Request) -> dict:
    identity = resolve_identity(request)
    return service.ask_supply_chain(
        payload.question,
        actor=f"{identity.display_name} · {identity.title}",
    )


@app.get("/api/inventory-risk", tags=["analytics"])
def get_inventory_risk(part_id: str, plant_id: str | None = None) -> dict:
    return service.get_inventory_risk(part_id, plant_id)


@app.get("/api/order-impact", tags=["analytics"])
def trace_order_impact(
    part_id: str,
    delay_days: int = Query(ge=1, le=90),
    supplier_id: str | None = None,
) -> dict:
    return service.trace_order_impact(part_id, delay_days, supplier_id)


@app.get("/api/approved-alternatives", tags=["mitigation"])
def list_approved_alternatives(
    part_id: str,
    plant_id: str,
    disrupted_supplier_id: str | None = None,
    delay_days: int = Query(default=14, ge=1, le=90),
) -> dict:
    return service.list_approved_alternatives(
        part_id,
        plant_id,
        delay_days,
        disrupted_supplier_id,
    )


@app.post("/api/mitigations/draft", tags=["mitigation"])
def draft_mitigation(payload: DraftMitigationRequest, request: Request) -> dict:
    identity = resolve_identity(request)
    require_role(identity, "SUPPLY_PLANNER")
    return service.draft_mitigation(
        payload.disruption_context,
        payload.selected_mitigation_option,
        f"{identity.display_name} · {identity.title}",
        identity.actor_id,
    ).model_dump()


@app.get("/api/mitigations", tags=["approvals"])
def list_mitigations(request: Request, status: str | None = None) -> dict:
    identity = resolve_identity(request)
    require_any_role(identity, "SUPPLY_PLANNER", "MITIGATION_APPROVER")
    return service.list_mitigations(status)


@app.post("/api/mitigations/{action_id}/approve", tags=["approvals"])
def approve_mitigation(action_id: str, payload: ApprovalRequest, request: Request) -> dict:
    identity = resolve_identity(request)
    require_role(identity, "MITIGATION_APPROVER")
    return service.approve_mitigation(
        action_id,
        f"{identity.display_name} · {identity.title}",
        identity.actor_id,
        payload.expected_version,
        payload.reason,
        payload.idempotency_key,
    ).model_dump()


@app.post("/api/mitigations/{action_id}/return-for-revision", tags=["approvals"])
def return_mitigation_for_revision(action_id: str, payload: RevisionRequest, request: Request) -> dict:
    identity = resolve_identity(request)
    require_role(identity, "MITIGATION_APPROVER")
    return service.return_mitigation_for_revision(
        action_id,
        f"{identity.display_name} · {identity.title}",
        payload.reason,
        identity.actor_id,
        payload.expected_version,
        payload.idempotency_key,
    ).model_dump()


@app.get("/api/audit-events", tags=["approvals"])
def audit_events(request: Request) -> dict:
    identity = resolve_identity(request)
    require_any_role(identity, "SUPPLY_PLANNER", "MITIGATION_APPROVER")
    return {
        "audit_events": service.repo.audit_events,
        "append_only": True,
        "source_system": service.repo.source_system,
    }
