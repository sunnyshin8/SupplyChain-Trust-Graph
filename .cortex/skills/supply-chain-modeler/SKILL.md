---
name: supply-chain-modeler
description: Maintains the supply-chain ontology, governed metric definitions, and Snowflake semantic model. Use when adding entities, relationships, dimensions, facts, metrics, or verified analytical questions.
---

# Supply Chain Modeler

## Source of truth

Treat `snowflake/001_schema.sql`, `snowflake/003_governed_semantic_views.sql`, `snowflake/005_security_zones.sql`, and `snowflake/ontology.yaml` as governed contracts. Snowflake owns shared definitions; the MCP server consumes them and must not redefine them conversationally.

## Workflow

1. Identify the affected entity, relationship, or metric.
2. Confirm every join uses a declared primary/foreign key relationship.
3. Define a metric once, including grain, filters, time behavior, and null handling.
4. Add or update a deterministic verified query.
5. Compare fixture-mode output with the Snowflake SQL result.
6. Run `make snowflake-validate` with the least-privilege runtime connection and require an explicit `PASS` result, including the legacy CORE denial.
7. Report the Snowflake query IDs from the validation output. Do not claim a semantic-view result without its query ID.
8. Reject the change if the same question can produce different definitions across paths.

## Governed metrics

- `revenue_at_risk`: Sum open-order value only when projected supply arrives after the customer-required date and allocatable stock cannot cover the order. Protect safety stock.
- `on_time_delivery_rate`: Deliveries received on or before promised date divided by deliveries due.
- `plant_stockout_risk`: Inventory plus confirmed inbound supply is below projected demand during the lead-time window.

## Validation contract

- Never create a metric from a prompt alone.
- Never use an undeclared relationship or many-to-many shortcut.
- Include source system, source timestamp, and definition version in important outputs.
- Return `INSUFFICIENT_EVIDENCE` when required keys or source records are absent.
