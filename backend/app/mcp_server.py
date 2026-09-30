from __future__ import annotations

import os
from typing import Any

from mcp.server.fastmcp import FastMCP

from .models import DisruptionContext, MitigationOption
from .policy import IDENTITIES
from .service import EvidenceError, GovernanceAuthorizationError, service


mcp = FastMCP(
    "Supply Chain Management MCP Server",
    instructions=(
        "Use governed source records only. Keep analysis, recommendation, draft, approval, "
        "and execution distinct. Never invent a supplier, source, metric, or result."
    ),
)


def _safe(callable_: Any, *args: Any) -> dict[str, Any]:
    try:
        return callable_(*args)
    except EvidenceError as exc:
        return {
            "status": "INSUFFICIENT_EVIDENCE",
            "detail": str(exc),
            "source_system": service.repo.source_system,
        }
    except GovernanceAuthorizationError as exc:
        return {"status": "REJECTED_BY_POLICY", "detail": str(exc)}
    except ValueError as exc:
        return {"status": "REJECTED_BY_POLICY", "detail": str(exc)}


@mcp.tool()
def analyze_supplier_delay(supplier_id: str, delay_days: int) -> dict[str, Any]:
    """Trace a supplier delay through parts, plants, inventory, shipments, orders, and customers."""
    return _safe(service.analyze_supplier_delay, supplier_id, delay_days)


@mcp.tool()
def compare_disruption_scenarios(
    supplier_id: str,
    delay_days: list[int],
) -> dict[str, Any]:
    """Compare governed impact across one to eight supplier-delay scenarios."""
    return _safe(service.compare_delay_scenarios, supplier_id, delay_days)


@mcp.tool()
def ask_supply_chain(question: str) -> dict[str, Any]:
    """Answer a natural-language supply-chain question through allowlisted governed tools only."""
    return _safe(service.ask_supply_chain, question)


@mcp.tool()
def get_inventory_risk(part_id: str, plant_id: str | None = None) -> dict[str, Any]:
    """Return governed inventory, safety stock, inbound supply, shortage date, and risk level."""
    return _safe(service.get_inventory_risk, part_id, plant_id)


@mcp.tool()
def trace_order_impact(
    part_id: str,
    delay_days: int,
    supplier_id: str | None = None,
) -> dict[str, Any]:
    """Identify affected open sales orders and calculate governed revenue at risk."""
    return _safe(service.trace_order_impact, part_id, delay_days, supplier_id)


@mcp.tool()
def list_approved_alternatives(
    part_id: str,
    plant_id: str,
    disrupted_supplier_id: str | None = None,
    delay_days: int = 14,
) -> dict[str, Any]:
    """List only qualified supplier-part-plant alternatives, ranked with explicit trade-offs."""
    return _safe(
        service.list_approved_alternatives,
        part_id,
        plant_id,
        delay_days,
        disrupted_supplier_id,
    )


@mcp.tool()
def draft_mitigation(
    disruption_context: DisruptionContext,
    selected_mitigation_option: MitigationOption,
) -> dict[str, Any]:
    """Create a PENDING_APPROVAL action draft; never execute a supplier or purchase-order change."""
    actor_id = os.getenv("SUPPLYCHAIN_MCP_ACTOR_ID", "").strip().lower()
    identity = IDENTITIES.get(actor_id)
    if identity is None or "SUPPLY_PLANNER" not in identity.roles:
        return {
            "status": "REJECTED_BY_POLICY",
            "detail": (
                "MCP drafting requires an allowlisted SUPPLYCHAIN_MCP_ACTOR_ID "
                "with the SUPPLY_PLANNER role."
            ),
        }
    action = _safe(
        service.draft_mitigation,
        disruption_context,
        selected_mitigation_option,
        f"{identity.display_name} · {identity.title}",
        identity.actor_id,
    )
    return action.model_dump() if hasattr(action, "model_dump") else action


if __name__ == "__main__":
    mcp.run(transport="stdio")
