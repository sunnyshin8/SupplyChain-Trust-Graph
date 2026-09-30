# Project decisions

## One intelligent service

The MVP uses one FastAPI/MCP service with internal workflow methods. This keeps tracing, metric logic, governance checks, and audit correlation in one transaction boundary without introducing microservice overhead.

## Next.js business experience

The dashboard uses Next.js App Router and TypeScript. It is a light enterprise interface using warm white, indigo, cobalt, amber, and coral—no dark theme, neon treatment, or green status language. Motion communicates data flow and state changes while respecting `prefers-reduced-motion`.

## Deterministic local first, Snowflake ready

Fixture mode makes judging reliable without credentials. The same entities, keys, values, and metric definitions appear in Snowflake DDL/seed artifacts. A repository adapter is the only required production swap.

## Layered Snowflake security zones

The database is separated by responsibility: private normalized sources, governed read-only analytics and semantic views, mutable mitigation workflow state, and append-only audit evidence. Schemas improve access isolation and ownership clarity; they are not treated as a performance feature. Runtime speed comes from narrow governed projections, one reused connection, and a short refreshable snapshot cache. The migration is additive so existing hackathon evidence is preserved while application roles are removed from legacy `CORE`.

## Metric code is not delegated to AI

Revenue at risk, OTD, and stockout risk are deterministic functions and governed SQL views. Natural language can select a tool or explain a result, but cannot create a formula or alter a threshold.

CoCo Cortex Analyst is used as a credit-backed natural-language-to-SQL layer over the native semantic view. Generated SQL is never trusted directly: a harness rejects writes, multiple statements, raw zones, and undeclared relations, then verifies exact business results and records attributable audit evidence. A three-scenario parity gate separately catches drift between Python workflow logic and governed Snowflake SQL.

## Governed conversation, not a generic chatbot

The natural-language layer is an allowlisted intent router over deterministic MCP tools. It extracts explicit governed identifiers, asks for clarification instead of inferring required fields, cites tool/source lineage, and rejects policy-bypass requests. This makes the conversational experience demonstrable without allowing generated prose to become the source of a business fact.

## Conservative order impact

Allocatable stock is `on_hand - safety_stock`. Open orders are processed by required date. An order is at risk when allocatable stock cannot cover it and delayed confirmed inbound arrives after its required date. This yields a reproducible `$586,000` for the demo.

## Approved alternatives only

Ranking occurs only after a qualification check on the exact supplier-part-plant combination. Fast but unapproved `SUP-031` exists in the data to prove the negative control: it is never recommended and a direct draft attempt fails.

## Explicit action states

The workflow distinguishes analysis, recommendation, draft, approval, and external execution. The MVP implements the first four; external execution is deliberately absent. This is safer and easier to defend than a fake purchase-order integration.

Approval uses an allowlisted demo-principal seam with distinct planner and approver roles. The server—not the request body—derives the actor. It also enforces separation of duties, optimistic action versions, idempotency keys, and a fresh supplier-qualification check. Enterprise deployment should replace the demo principal header with verified SSO/JWT claims.

## Audit implementation trade-off

Local fixture-mode audit and action state is in memory for a zero-credential fallback. In deployed Snowflake mode, actions, decisions, idempotency records, and audit events persist in separate `WORKFLOW` and `AUDIT` schemas. The runtime may insert but cannot update or delete audit evidence; action plus audit writes commit atomically.
