---
name: disruption-investigator
description: Investigates supplier disruptions through the governed Supplier-to-Part-to-Plant-to-Shipment-to-Order-to-Customer graph. Use when a delay, shortage, shipment exception, stockout, or customer-impact question is raised.
---

# Disruption Investigator

## Investigation workflow

1. Validate `supplier_id` and `delay_days`; do not infer missing identifiers.
2. Call the registered `supplychain-trust-graph` MCP tool `analyze_supplier_delay` with those exact inputs. Do not calculate the answer in the model.
3. Use the returned correlation ID for the complete investigation.
4. Resolve the graph in this order: Supplier → Part → Plant → Inventory → Shipment → Sales Order → Customer.
5. For each returned part/plant pair, call `get_inventory_risk`; call `trace_order_impact` for each distinct part.
5. Calculate revenue at risk using the versioned metric definition.
6. Attach supplier notices, shipment records, calculation assumptions, source systems, and timestamps.
8. Confirm every displayed figure exists in the structured MCP result and report the MCP tool names, correlation ID, source references, source system, snapshot time, and Snowflake query IDs when present.
9. Append an `INVESTIGATION_COMPLETED` audit event only through the MCP service.

## Response contract

Return affected parts, plants, shipments, open orders, customer tiers, revenue at risk, risk severity, source references, assumptions, correlation ID, and generated timestamp.

## Safety rules

- Analysis is read-only.
- Never invent a shipment, order, customer, source, date, or metric result.
- Mark conclusions separately from assumptions.
- If source evidence is missing, return `INSUFFICIENT_EVIDENCE` with the missing record type.
