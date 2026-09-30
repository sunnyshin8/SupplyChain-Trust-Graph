# CoCo CLI and Snowflake evidence

Verified on 2026-09-30 against the live Snowflake account. No password, OAuth code, access token, or PAT is stored in this repository.

## CoCo CLI

- Official Cortex Code CLI installed: `v1.1.87`.
- Separate named OAuth connections are configured for least-privilege runtime use and explicitly authorized administration.
- Project skill discovery verified with `cortex skill list`:
  - `conversational-analyst`
  - `disruption-investigator`
  - `mitigation-planner`
  - `supply-chain-modeler`
  - `trust-evaluator`
- Local stdio MCP server registered and verified with `cortex mcp get supplychain-trust-graph`.
- A real read-only CoCo agent prompt was attempted against the live MCP server. The account returned: `Cortex Code is not enabled or the usage limit has been reached.` Request ID: `9c871219-391e-4df5-bfcb-e2b2ef3f7b83`. This is an account entitlement/usage blocker, not a project wiring error.
- CoCo started the registered MCP runtime successfully. The current MCP contract exposes seven governed tools, including multi-delay scenario comparison.
- After the layered migration and runtime gate passed, the global CoCo registration was switched from fixture mode to `SUPPLYCHAIN_DATA_MODE=snowflake` with the least-privilege connection and allowlisted planner principal `maya.iyer`. `cortex mcp get supplychain-trust-graph` and `cortex mcp start` both confirmed the live configuration.

## Credit-backed CoCo Cortex Analyst proof

`make coco-analyst-eval` now runs a repeatable three-question evaluation through the installed CoCo CLI and Snowflake Cortex Analyst. It accepts only one read-only statement and only the declared semantic view or its declared `GOVERNED.ORDER_RISK` logical table; DDL, DML, multiple statements, `CORE`, `SOURCE`, workflow, audit, and unknown relations are rejected before execution. All three live cases passed:

- golden metrics: `$586,000`, 3 orders, `SUP-042` — CoCo request `dd61ab56-d691-433a-bef6-aa6d64117bf2`; Snowflake query `01c76b94-000e-08bd-0002-51660008a0ca`
- affected orders: `SO-7101`, `SO-7102`, and `SO-7103`, with the expected customer names and tiers — CoCo request `77284144-069d-48ad-8c44-f927d8028b3e`; Snowflake query `01c76b94-000e-0899-0002-5166000890f2`
- plant breakdown: Pune `$390,000` / 2 orders and Bengaluru `$196,000` / 1 order — CoCo request `deb01c4f-4155-46ed-bb13-c46563d3f066`; Snowflake query `01c76b94-000e-08bd-0002-51660008a0ce`

The suite persisted one attributable `CORTEX_ANALYST_EVAL` audit event, `AUD-COCO-EVAL-7FE3B17F`, with `SOURCE_SYSTEM='COCO_CLI'`. Insert query: `01c76b94-000e-08ab-0002-516600090016`; uniqueness proof: `01c76b94-000e-08ab-0002-51660009001a`.

The narrower single-question harness also passed with CoCo request `90b1fe1c-9d5f-4916-9d46-1d8bed9d6a98`, semantic query `01c76a06-000e-08ab-0002-516600087086`, and audit `AUD-COCO-369874E1`.

## Native Cortex Agent readiness

Migration `007_cortex_agent.sql` deployed a secure `SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLYCHAIN_TRUST_AGENT` with one read-only Analyst tool, a 45-second / 8,000-token budget, inaccessible-tool rejection, and an explicit no-execution/no-fabrication response policy. The runtime role can list the agent, and the admin role can describe the semantic-view binding. Deployment assertion query: `01c76a10-000e-08ab-0002-5166000870ea`.

The live Agent Studio test reached Snowflake but the account rejected invocation with `399504: Access denied for trial accounts` (request `90ac485e-e98c-43c4-aa3f-9882996d2258`). The object, role grants, discovery, and tool binding are deployed; native agent execution requires a paid account or eligible Cortex Agents trial. This does not affect the working credit-backed Cortex Analyst path above.

## Snowflake connection proof

The shared OAuth profile successfully executed a read-only context query:

- Account: `KJ18976`
- Role: `ACCOUNTADMIN`
- Warehouse: `COMPUTE_WH`
- Region: `AWS_AP_SOUTHEAST_7`
- Snowflake version: `10.35.101`
- Query ID: `01c763d3-000e-07d0-0002-516600063052`

Read-only entitlement diagnostics ruled out the two common configuration causes:

- CoCo CLI daily credit limit is `-1` (unlimited), query ID `01c763d9-000e-07ba-0002-516600067032`.
- The role can enumerate 107 Cortex base models, query ID `01c763d9-000e-07bc-0002-51660006a01e`.

That leaves account entitlement/trial type as the likely blocker. Snowflake documents that CoCo CLI is not available on standard Snowflake trial accounts; it requires a paid account or the dedicated CoCo CLI trial.

## Deployed Snowflake application proof

The approved `ACCOUNTADMIN` deployment completed on 2026-09-30 using the existing `COMPUTE_WH`; the harness did not create a warehouse.

- `001_schema.sql`: PASS — database/schema, governed tables, append-only audit and idempotency tables, `SUPPLYCHAIN_APP_READONLY` and `SUPPLYCHAIN_APP_RUNTIME` roles/grants.
- `002_seed.sql`: PASS — deterministic demo data.
- `003_governed_semantic_views.sql`: PASS — governed relational views and the native semantic view. Golden result: `$586,000`, 3 affected orders, supplier `SUP-042` (query ID `01c769c5-000e-089a-0002-516600083122`).
- `004_validation.sql`: PASS — golden metric and unapproved-supplier negative control (last validation query ID `01c769c5-000e-0899-0002-516600081166`).
- `005_security_zones.sql`: PASS — private `SOURCE`, read-only `GOVERNED`, mutable `WORKFLOW`, append-only `AUDIT`, migrated state, and direct legacy-object isolation (query ID `01c769c5-000e-089a-0002-516600083156`).
- `006_core_isolation_fix.sql`: PASS — residual grants materialized by the earlier future-view grant are absent (query ID `01c76a10-000e-089a-0002-5166000832de`).
- `007_cortex_agent.sql`: PASS — secure, read-only Cortex Agent, dedicated agent database-role grants, and existence assertion (query ID `01c76a10-000e-08ab-0002-5166000870ea`).
- `008_quantity_aware_scenarios.sql`: PASS — forward-only quantity-aware allocation, governed/semantic view parity, and `$586,000` / 3-order baseline assertion (query ID `01c76b93-000e-08ce-0002-51660009100a`).

The latest deployment context was account `KJ18976`, role `ACCOUNTADMIN`, warehouse `COMPUTE_WH`, region `AWS_AP_SOUTHEAST_7` (query ID `01c76a0f-000e-089a-0002-51660008328e`). The admin profile is deployment-only. The deploy harness was hardened to fail when an assertion query returns scalar `FAIL`; it no longer confuses statement execution with validation success.

The multi-delay metric-drift gate also passed 3/3 with secondary roles disabled: 3 days = `$0` / 0 orders, 7 days = `$436,000` / 2 orders, and 14 days = `$586,000` / 3 orders in both Python and live governed Snowflake SQL. Query ID: `01c76b94-000e-08ce-0002-51660009100e`.

The runtime release gate then passed through the least-privilege `SUPPLYCHAIN_APP_RUNTIME` role:

- context with secondary roles disabled: PASS (query ID `01c769c2-000e-07bd-0002-5166000850ce`)
- golden governed metric: PASS — `$586,000` across 3 orders (query ID `01c769c2-000e-0886-0002-51660007f102`)
- unapproved supplier exclusion: PASS — 0 leaked rows (query ID `01c769c2-000e-07bd-0002-5166000850d2`)
- native semantic view query: PASS (query ID `01c769c2-000e-089a-0002-5166000830ea`)
- `WORKFLOW` read: PASS (query ID `01c769c2-000e-07bd-0002-5166000850d6`)
- `AUDIT` read: PASS (query ID `01c769c2-000e-089a-0002-5166000830ee`)
- direct `CORE.SUPPLIERS` read: expected denial PASS (query ID `01c769c2-000e-0898-0002-5166000840d6`)

## Layered security migration status

`snowflake/005_security_zones.sql` and the idempotent forward-fix `006_core_isolation_fix.sql` are deployed. Both final isolation assertions returned `PASS`. An initial validator run exposed that the developer login's secondary roles could still confer admin access despite `CURRENT_ROLE=SUPPLYCHAIN_APP_RUNTIME`. The repository and validator now execute `USE SECONDARY ROLES NONE`; the repeated runtime test then proved direct `CORE` denial while governed, semantic, workflow, and audit paths stayed healthy.

The FastAPI service runs in real Snowflake mode with that runtime profile. The read-only Snowflake repository scorecard passed 4/4; its semantic query returned `$586,000`, 3 orders, and `SUP-042` (query ID `01c769c4-000e-0886-0002-51660007f116`). A fresh durable write-path probe created action `ACT-FA72568A`, rejected planner self-approval with HTTP 403, approved version 2 as an independent approver, replayed the same idempotency key without duplication, and found exactly one approval audit row (`AUD-546F32DB`; draft audit `AUD-10C02E03`). No ERP or purchase-order action was executed.

## Browser and release proof

- The real Snowflake-backed Next.js application was opened at `http://127.0.0.1:3000` in the VS Code integrated browser.
- The rendered dashboard showed `$586K`, 3 risky orders, 2 plants, semantic-view evidence, and the persisted Snowflake audit records.
- The **Ask graph** control returned a grounded `$586,000` answer with four source references; the API recorded `POST /api/conversation` with HTTP 200.
- The integrated DevTools console contained only the normal React DevTools suggestion and `[HMR] connected`; no runtime errors were present.
- Current local release gates: 52 backend tests PASS, Next.js lint, standalone production build, and Snowflake static-export build PASS, 6/6 fixture release scorecard PASS, and 4/4 live Snowflake scorecard PASS. The added tests cover truthful zero-risk narrative/provenance, quantity-aware scenario thresholds, lead-time-aware alternatives, Snowflake ingress identity, durable multi-action approval inboxes, actor-bound idempotency, authenticated MCP ownership, layered schemas, CORE denial grants, disabled secondary-role inheritance, dedicated hosting ownership, live dependency health/reconnect, portable static web packaging, assertion-aware deployments, governed repository paths, explicit Snowflake transactions, CoCo-generated SQL bypass probes, multi-delay Snowflake parity, and removal of the stockout-view supplier hardcode.

## Reproduce

```bash
cortex connections list
cortex skill list
cortex mcp get supplychain-trust-graph
make snowflake-deploy
make snowflake-validate
make snowflake-parity
make backend-snowflake
make live-api-verify
make coco-analyst-verify
make coco-analyst-eval
```

`make snowflake-deploy` creates persistent database objects, roles, grants, and seed data with the configured role. Run it only after the account owner explicitly authorizes that privileged deployment. `make snowflake-validate` uses the runtime role and is read-only. `make live-api-verify` writes one controlled mitigation draft plus its approval/audit records; it never executes an ERP or purchase-order action.
