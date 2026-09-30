# Three-minute demo script

## Setup

Run `make backend-snowflake` and `make frontend`, then open `http://127.0.0.1:3000`. Run `make coco-analyst-eval` once before judging so the top bar and audit trail show the live **CoCo credits · 3/3 verified** evidence. The deployed demo may already contain approved verification actions; the judging flow creates a new attributable draft.

## 1. Open the control tower

Say: “A normal chatbot can explain a supply-chain problem. SupplyChain Trust Graph calculates the governed impact, proves it with evidence, and prepares a safe human-approved action.”

Point out the five executive signals: one active disruption, `$586K` revenue at risk, two plants at stockout risk, three orders at risk, and the approval queue.

## 2. Ask the trust graph

Open **Ask the trust graph** and submit: “What revenue is at risk if SUP-042 is delayed by 14 days?”

Show the deterministic answer, three facts, invoked tools, correlation ID, audit ID, and clickable source references. Explain that missing identifiers produce a clarification response and policy-bypass prompts are rejected rather than sent to a free-form model.

Point to **CoCo credits · 3/3 verified** in the top bar. Explain that a separate repeatable CoCo CLI evaluation used Cortex Analyst credits against the same governed semantic view for the golden metric, exact affected orders, and plant-level breakdown; its request/query IDs are recorded in the Snowflake audit trail.

## 3. Investigate SUP-042

Scroll to **Trace the blast radius**. Keep supplier `SUP-042` and delay `14 days`, then select **Run investigation**.

Show the animated path:

```text
Supplier → Part → Plant → Shipment → Order → Customer
```

Explain that two parts and two inbound shipments expose three customer orders. Two affected customers are strategic.

## 4. Prove the calculation

Show the governed explanation and order list. State:

- `SO-7101` = `$240,000`
- `SO-7102` = `$150,000`
- `SO-7103` = `$196,000`
- governed revenue at risk = **`$586,000`**

Explain that `SO-7104` is excluded because the revised inbound date is still before its required date. Safety stock remains protected.

## 5. Inspect evidence

Open **Every answer has a source**. Show:

- supplier notice `DOC-042-09`
- shipment exceptions `SHP-8801` and `SHP-8802`
- governed metric `METRIC-RAR-V1`
- source systems, timestamps, and explicit assumptions

Say: “If a source is missing, the server responds with insufficient evidence. It never fills the gap conversationally.”

## 6. Plan mitigation

Open **Choose a safe recovery path**. Show that the UI presents only approved alternatives and explicitly excluded one unapproved qualification.

Select `SUP-017 · Axis Precision Works`. Explain the trade-off: five-day lead time, 500 units of capacity, 77% coverage, and an 8–11% premium.

## 7. Draft, do not execute

Act as **Maya · Planner**, then select **Create mitigation draft**. Show status `PENDING APPROVAL`, assigned owner, action version, policy decision ID, action ID, audit ID, and the new audit event.

Say: “The MCP server has not changed a supplier or created a purchase order. It has prepared an attributable draft.”

## 8. Record independent human approval

Show that the approval buttons are unavailable to Maya. Switch to **Aisha · Approver**, then select **Approve action**. Show the named approver, incremented action version, qualification recheck, and attributable audit entry. Emphasize that approval is recorded while downstream ERP execution remains a separate integration boundary.

## Closing

“Snowflake owns the governed ontology and shared metrics. The Supply Chain Management MCP Server traces and coordinates the decision. CoCo CLI packages the repeatable modeling, investigation, and mitigation workflows. The dashboard makes the trusted answer usable by operations leaders.”
