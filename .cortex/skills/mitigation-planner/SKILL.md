---
name: mitigation-planner
description: Ranks qualified supply alternatives and prepares approval-safe mitigation drafts. Use when users ask how to recover from a shortage, select another supplier, protect customer orders, or draft a mitigation action.
---

# Mitigation Planner

## Planning workflow

1. Require a completed disruption context with its correlation ID.
2. Query approved `SupplierPart` records for the exact part and plant.
3. Exclude the disrupted supplier and every unapproved supplier.
4. Rank eligible options using lead time, available capacity, cost band, and protected customer impact.
5. Explain the trade-off and cite the qualification record.
6. Confirm the MCP server reports an allowlisted `SUPPLYCHAIN_MCP_ACTOR_ID` with the `SUPPLY_PLANNER` role. Never pass a free-text owner.
7. On explicit user selection, call the `draft_mitigation` MCP tool and require `PENDING_APPROVAL` status.
8. Append a `MITIGATION_DRAFTED` audit event through the MCP service and return its audit ID.

## Approval boundary

- A draft is not an executed action.
- Never create or change a purchase order, supplier assignment, shipment, or ERP record.
- Only an authorized human may approve a draft.
- Approval is recorded separately from downstream execution.
- Reject any option whose supplier-part-plant approval cannot be proven.

## Output contract

Return ranked approved alternatives, lead time, available capacity, cost band, coverage, trade-off, source system, draft owner, status, action ID, audit ID, and correlation ID.
