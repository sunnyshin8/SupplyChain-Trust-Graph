# Project decisions

## One intelligent service

The MVP uses one FastAPI/MCP service with internal workflow methods. This keeps tracing, metric logic, governance checks, and audit correlation in one transaction boundary without introducing microservice overhead.

## Next.js business experience

The dashboard uses Next.js App Router and TypeScript. It is a light enterprise interface using warm white, indigo, cobalt, amber, and coral no dark theme, neon treatment, or green status language. Motion communicates data flow and state changes while respecting `prefers-reduced-motion`.

## Deterministic local first, Snowflake ready

Fixture mode makes judging reliable without credentials. The same entities, keys, values, and metric definitions appear in Snowflake DDL/seed artifacts. A repository adapter is the only required production swap.

## Layered Snowflake security zones

The database is separated by responsibility: private normalized sources, governed read-only analytics and semantic views, mutable mitigation workflow state, and append-only audit evidence. Schemas improve access isolation and ownership clarity; they are not treated as a performance feature. Runtime speed comes from narrow governed projections, one reused connection, and a short refreshable snapshot cache. The migration is additive so existing validation evidence is preserved while application roles are removed from legacy `CORE`.

## Metric code is not delegated to AI

Revenue at risk, OTD, and stockout risk are deterministic functions and governed SQL views. Natural language can select a tool or explain a result, but cannot create a formula or alter a threshold.

CoCo Cortex Analyst is used as a credit-backed natural-language-to-SQL layer over the native semantic view. Generated SQL is never trusted directly: a harness rejects writes, multiple statements, raw zones, and undeclared relations, then verifies exact business results and records attributable audit evidence. A three-scenario parity gate separately catches drift between Python workflow logic and governed Snowflake SQL.

## Governed conversation, not a generic chatbot

The natural-language layer is an allowlisted intent router over deterministic MCP tools. It extracts explicit governed identifiers, asks for clarification instead of inferring required fields, cites tool/source lineage, and rejects policy-bypass requests. This makes the conversational experience demonstrable without allowing generated prose to become the source of a business fact.

## Quantity-aware order impact

Allocatable stock is `on_hand - safety_stock`. Confirmed inbound supply is accumulated by projected arrival date, while open demand is accumulated by customer-required date within each part/plant partition. Only the selected disrupted supplier receives the scenario delay; unaffected inbound retains its recorded promise date. An order is at risk when cumulative supply available by its required date is below cumulative demand. This yields a reproducible `$586,000` at 14 days while preserving the zero-risk 3-day case.

## Approved alternatives only

Ranking occurs only after a qualification check on the exact supplier-part-plant combination. Fast but unapproved `SUP-031` exists in the data to prove the negative control: it is never recommended and a direct draft attempt fails.

## Explicit action states

The workflow distinguishes analysis, recommendation, draft, approval, and external execution. The MVP implements the first four; external execution is deliberately absent. This is safer and easier to defend than a fake purchase-order integration.

Local fixture mode uses an allowlisted demonstration-principal seam. Snowflake-hosted mode ignores that header and derives the actor from the `Sf-Context-Current-User` identity injected by authenticated Snowpark Container Services ingress. Deployment requires non-overlapping planner and approver Snowflake-user allowlists. The server also enforces separation of duties, optimistic action versions, actor-bound idempotency keys, and a fresh supplier-qualification/capacity check inside the decision transaction.

## Separate service and data planes

`SUPPLYCHAIN_APP_RUNTIME` is a non-human data role and never receives the public endpoint's `UI_USAGE` service role. A distinct `SUPPLYCHAIN_APP_SERVICE_OWNER` owns the one Snowpark service and inherits the narrower runtime data role, as required for Snowflake-provided service credentials. Deployment temporarily grants it service-creation and endpoint-binding privileges, then revokes both after the service is updated. Because Snowflake does not support transferring ownership of a `SERVICE`, the runtime service identity necessarily retains ownership controls over its own service; it cannot create another service or bind another endpoint after deployment.

## Audit implementation trade-off

Local fixture-mode audit and action state is in memory for a zero-credential fallback. In deployed Snowflake mode, actions, decisions, idempotency records, and audit events persist in separate `WORKFLOW` and `AUDIT` schemas. The runtime may insert but cannot update or delete audit evidence; action plus audit writes commit atomically.
