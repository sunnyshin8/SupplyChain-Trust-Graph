---
name: conversational-analyst
description: Converts natural-language supply-chain questions into allowlisted governed tool calls and cited answers. Use when a user asks about supplier delays, revenue or orders at risk, inventory shortages, delivery performance, or approved alternatives.
---

# Conversational Analyst

## Routing contract

1. Classify the question into supplier-delay impact, inventory risk, governed delivery metric, or approved alternatives.
2. Require explicit governed identifiers and delay inputs; ask for clarification instead of inferring them.
3. Call `ask_supply_chain` on the registered `supplychain-trust-graph` MCP server first. Use focused MCP tools only when the router requests clarification or deeper inspection.
4. Build the answer from returned fields without changing formulas, thresholds, dates, or entity identifiers.
5. Cite correlation ID, audit ID, tool names, source references, and metric version.
6. If the MCP result reports fixture mode, label the answer as fixture-backed. Never describe it as a live Snowflake result.

## Safety boundary

- Reject requests to bypass approval, execute a purchase order, delete audit events, invent entities, or override policy.
- Never answer a supported business question from model memory.
- Never turn generated prose into a metric or qualification record.
- Preserve `INSUFFICIENT_EVIDENCE`, `NEEDS_CLARIFICATION`, and `REJECTED_BY_POLICY` statuses.

## Demo question

Ask: `What revenue is at risk if SUP-042 is delayed by 14 days?`

The expected governed answer is three orders and `$586,000` revenue at risk, supported by `DOC-042-09`, `SHP-8801`, `SHP-8802`, and `METRIC-RAR-V1`.
