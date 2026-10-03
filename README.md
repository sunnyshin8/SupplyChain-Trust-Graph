# SupplyChain Trust Graph

Supplier disruptions are usually detected in one system, explained in another, and acted on in a third. By the time an operations team connects the affected parts, plants, shipments, customer orders, and qualified alternatives, the commercial impact may already have grown and a fast response can still introduce new risk if it relies on an unapproved supplier or an unaudited action.

**SupplyChain Trust Graph closes that decision gap.** It traces a disruption through a governed business graph, calculates impact with deterministic metrics, proves every answer with source evidence, ranks only qualified recovery options, and keeps mitigation behind an explicit human-approval boundary.

> It is not a chatbot that invents a plausible answer. It resolves governed entities, applies versioned business rules, returns evidence and lineage, and fails closed when data is insufficient.

## What the system delivers

- **End-to-end impact tracing:** supplier → part → plant → inventory → shipment → sales order → customer.
- **Consistent metrics:** revenue at risk, on-time delivery, and stockout risk come from governed definitions rather than generated prose.
- **Decision-threshold simulation:** planners compare 3/7/14/21-day scenarios and see the first delay that creates material customer exposure.
- **Evidence-backed answers:** results include source records, timestamps, correlation IDs, audit IDs, and Snowflake query IDs when available.
- **Guarded conversational analytics:** natural-language questions route only to allowlisted deterministic tools or guarded Cortex Analyst queries.
- **Safe recovery planning:** only approved supplier-part-plant qualifications can become mitigation options.
- **Human-controlled actions:** planners create drafts; a separate authorized approver records the decision; ERP execution stays outside the trust boundary.
- **Durable approval inbox:** pending drafts reload from `WORKFLOW`, duplicate active mitigations are rejected, and approval revalidates live qualification and capacity inside the decision transaction.
- **Durable governance:** Snowflake separates private source data, read-only analytics, workflow state, and append-only audit evidence.
- **Repeatable agent workflows:** Snowflake CoCo CLI discovers project skills for modeling, investigation, analysis, mitigation, and trust evaluation.
- **Snowflake-hosted UX:** a Next.js control tower and FastAPI service are packaged as Linux/AMD64 containers for a single Snowpark Container Services deployment.
- **Public read-only showcase:** a Streamlit Community Cloud surface reads the same Snowflake-governed contracts without requiring visitors to hold a Snowflake account.

## Reference scenario

The deterministic reference scenario models a 14-day delay from supplier `SUP-042`. The same entity keys and metric rules are represented in the local fixture repository and Snowflake.

| Governed result | Value |
| --- | ---: |
| Affected parts | 2 |
| Plants at risk | 2 |
| Delayed inbound shipments | 2 |
| Customer orders at risk | 3 |
| Strategic customers exposed | 2 |
| Governed revenue at risk | **$586,000** |

The revenue result is the sum of the three orders that fail the governed availability test:

- `SO-7101`: `$240,000`
- `SO-7102`: `$150,000`
- `SO-7103`: `$196,000`

`SO-7104` is excluded because supply is still projected to arrive before its required date. Safety stock is never treated as freely allocatable inventory.

## Decision flow

```mermaid
flowchart LR
    A[Supplier delay reported] --> B[Resolve governed graph]
    B --> C[Project inbound dates]
    C --> D[Protect safety stock]
    D --> E[Identify exposed orders]
    E --> F[Calculate governed impact]
    F --> G[Attach evidence and lineage]
    G --> H[Rank approved alternatives]
    H --> I[Planner creates draft]
    I --> J{Independent review}
    J -->|Approve| K[Record approved decision]
    J -->|Return| L[Return for revision]
    K --> M[External execution boundary]
```

Analysis, recommendation, drafting, approval, and execution are deliberately separate states. The application implements the first four; it never creates a purchase order or silently changes an ERP record.

## Architecture

```mermaid
flowchart TB
    UI[Next.js operations dashboard] --> API[FastAPI REST adapter]
    SPCS[Snowpark Container Services ingress] --> UI
    PUBLIC[Public Streamlit showcase] --> READONLY[Read-only service identity]
    READONLY --> GOVERNED
    COCO[Snowflake CoCo CLI] --> MCP[Supply Chain MCP server]
    COCO --> ANALYST[Cortex Analyst]
    API --> ENGINE[Deterministic workflow engine]
    MCP --> ENGINE
    ANALYST --> SEMANTIC[Native semantic view]
    ENGINE --> REPO[Governed repository contract]
    REPO --> FIXTURE[Local fixture repository]
    REPO --> SNOW[Snowflake repository]
    SNOW --> SOURCE[Private SOURCE zone]
    SNOW --> GOVERNED[Read-only GOVERNED zone]
    SNOW --> WORKFLOW[Mutable WORKFLOW zone]
    SNOW --> AUDIT[Append-only AUDIT zone]
```

### Next.js operations experience

The frontend uses Next.js App Router, React, and TypeScript. It provides:

- executive disruption and exposure signals;
- a natural-language question panel with grounded responses;
- an interactive supplier-to-customer blast-radius graph;
- order-level revenue impact and metric explanations;
- multi-delay scenario comparison with a visible materiality threshold;
- evidence inspection with source metadata;
- explicit recorded, derived, and scenario-projection evidence labels;
- approved-alternative comparison and trade-offs;
- planner and approver views with separation of duties;
- a durable pending-approval inbox, mitigation status, action versions, policy IDs, and audit history;
- explicit preview, fixture, and live Snowflake provenance states.

If the backend is unavailable, the UI may show a clearly labeled unverified preview so the interface remains inspectable. Investigations and every state-changing action fail closed; the browser never simulates a successful draft or approval.

### FastAPI and MCP service

One Python service contains the REST API, MCP surface, policy checks, workflow engine, and repository abstraction. Keeping these responsibilities inside one deployable preserves a single policy and transaction boundary without unnecessary distributed coordination.

The MCP server exposes seven typed tools:

| Tool | Responsibility |
| --- | --- |
| `ask_supply_chain(question)` | Route a natural-language request to an allowlisted governed workflow. |
| `analyze_supplier_delay(supplier_id, delay_days)` | Trace the complete disruption blast radius. |
| `compare_disruption_scenarios(supplier_id, delay_days[])` | Compare one to eight governed delay assumptions. |
| `get_inventory_risk(part_id, plant_id?)` | Return safety-stock-aware inventory exposure. |
| `trace_order_impact(part_id, delay_days, supplier_id?)` | Identify affected orders and calculate quantity-aware revenue at risk. |
| `list_approved_alternatives(part_id, plant_id, disrupted_supplier_id?, delay_days?)` | Rank only qualified recovery suppliers. |
| `draft_mitigation(disruption_context, selected_mitigation_option)` | Create an attributable `PENDING_APPROVAL` action. |

There is intentionally no MCP tool for executing a purchase order, changing a supplier assignment, or deleting audit history.

### Snowflake data plane

Snowflake is the governed source of truth in live mode. The model contains normalized business entities, declared relationships, shared metrics, least-privilege roles, a native semantic view, and a secure read-only Cortex Agent definition.

| Schema | Purpose | Runtime behavior |
| --- | --- | --- |
| `SOURCE` | Private normalized source data | Application roles cannot query it directly. |
| `GOVERNED` | Curated entities, metrics, and semantic access | Read-only for the application runtime. |
| `WORKFLOW` | Mitigation drafts, decisions, and idempotency state | Controlled inserts and versioned updates. |
| `AUDIT` | Attributable investigation and decision evidence | Append-only for the application runtime. |
| `CORE` | Backward-compatible migration layer | Explicitly denied to application roles after cutover. |

The runtime disables inherited secondary roles on every application connection. A developer session with a privileged secondary role therefore cannot silently widen service access.

## Governed metrics

### Revenue at risk

An open order contributes to revenue at risk when protected on-hand inventory plus all inbound quantities arriving by its required date cannot cover cumulative demand at that plant. Only shipments from the disrupted supplier receive the selected scenario delay; other confirmed inbound supply retains its recorded promise date.

```text
allocatable inventory = max(on hand - safety stock, 0)
available supply by required date = allocatable inventory + on-time inbound quantity
at risk = available supply by required date < cumulative order demand
revenue at risk = sum(order value for at-risk orders)
```

Orders are evaluated by required date so earlier demand consumes allocatable inventory first. The metric exists in deterministic Python and governed Snowflake SQL, then passes a multi-delay parity check.

### On-time delivery rate

```text
on-time delivery rate = deliveries received on or before promise date / deliveries due
```

### Plant stockout risk

A part-plant pair is at risk when on-hand inventory plus confirmed inbound supply inside the approved lead-time window is lower than projected demand for that window.

Metric definitions are never delegated to a language model. Natural language may select a metric and explain returned fields, but it cannot change the formula, threshold, grain, or source records.

## Governance and safety guarantees

- Analytical tools are read-only by default.
- Missing required identifiers produce `NEEDS_CLARIFICATION`.
- Missing governed records produce `INSUFFICIENT_EVIDENCE`.
- Policy-bypass and execution prompts produce `REJECTED_BY_POLICY`.
- Only an approved supplier-part-plant combination can be recommended or drafted.
- The server derives the actor from trusted Snowflake ingress identity in hosted mode or a strict allowlist in local mode, never from a request-body owner.
- Planner and approver roles remain separate; the draft owner cannot self-approve.
- Approval revalidates action version, supplier qualification, and capacity from Snowflake inside the write transaction.
- Idempotency keys prevent duplicate recorded decisions.
- Optimistic versions reject stale concurrent decisions.
- Action and audit writes share one explicit Snowflake transaction.
- Audit evidence is append-only to the application runtime.
- Approval records a decision but never executes it in an external system.

The local `X-Demo-Actor` header is accepted only in `SUPPLYCHAIN_IDENTITY_MODE=demo`. Snowflake hosting uses `SUPPLYCHAIN_IDENTITY_MODE=spcs`, ignores that header, and trusts the authenticated `Sf-Context-Current-User` value injected by Snowflake ingress. Planner and approver membership come from deployment-time allowlists, while owner separation is always enforced server-side.

## Snowflake CoCo CLI integration

CoCo CLI is a repeatable engineering and analysis surface, not a decorative wrapper. Project skills live under `.cortex/skills/` and are discovered when CoCo starts from the repository root.

| Skill | Use |
| --- | --- |
| `supply-chain-modeler` | Maintain ontology relationships, metrics, and verified queries. |
| `disruption-investigator` | Trace a governed supplier-to-customer impact path. |
| `conversational-analyst` | Convert business questions into allowlisted, cited tool calls. |
| `mitigation-planner` | Rank qualified alternatives and create approval-safe drafts. |
| `trust-evaluator` | Run metric, security, policy, MCP, and release gates. |

The registered MCP runtime uses a server-derived planner principal. CoCo can also invoke Cortex Analyst against the native semantic view. Generated SQL passes through a local guardrail before execution:

- exactly one read-only statement is allowed;
- DDL, DML, and multiple statements are rejected;
- raw source, legacy, workflow, audit, and unknown relations are rejected;
- only the declared semantic view or governed logical table is allowed;
- returned results are checked against exact expected values;
- an attributable evaluation event is written to the audit zone.

Start CoCo and verify discovery:

```bash
cortex -w .
cortex connections list
cortex skill list
cortex mcp get supplychain-trust-graph
```

Example CoCo requests:

```text
Use conversational-analyst to answer: What revenue is at risk if SUP-042 is delayed by 14 days?

Use disruption-investigator to investigate SUP-042 with a 14-day delay and cite every source record.

Use mitigation-planner to rank only approved alternatives for PRT-AX14 at PLT-PUN and prepare a draft.

Use trust-evaluator to run the release gates and adversarial policy probes.
```

See [COCO_EVIDENCE.md](COCO_EVIDENCE.md) for reproducible request, query, deployment, and entitlement evidence.

## Quick start: fixture mode

### Prerequisites

- Python 3.11+
- Node.js 20+
- npm
- `make`

### Install

```bash
make install
```

This creates `.venv`, installs the Python package with test dependencies, and installs the frontend packages.

### Run the backend

```bash
make backend
```

The API starts at [http://127.0.0.1:8000](http://127.0.0.1:8000), with OpenAPI documentation at [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs).

### Run the frontend

In a second terminal:

```bash
make frontend
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000). Next.js rewrites `/api/*` requests to the FastAPI service. Fixture mode is the default and needs no cloud credentials.

## Run the MCP server

The MCP service uses stdio transport:

```bash
cd backend
../.venv/bin/python -m app.mcp_server
```

For a Snowflake-backed MCP runtime:

```bash
PYTHONPATH="$PWD/backend" \
SUPPLYCHAIN_DATA_MODE=snowflake \
SNOWFLAKE_CONNECTION_NAME=supplychain-runtime \
SUPPLYCHAIN_MCP_ACTOR_ID=maya.iyer \
.venv/bin/python -m app.mcp_server
```

Do not put passwords, OAuth codes, private keys, or access tokens in the repository. Snowflake Connector and CoCo CLI use a password-free named connection from the user's Snowflake configuration.

## Snowflake deployment

Use separate named connections for deployment and runtime:

- an administrator connection for explicitly authorized schema and role creation;
- a least-privilege runtime connection for validation, reads, workflow writes, and CoCo/MCP use.

The deployment harness applies migrations in order:

```text
snowflake/001_schema.sql
snowflake/002_seed.sql
snowflake/003_governed_semantic_views.sql
snowflake/004_validation.sql
snowflake/005_security_zones.sql
snowflake/006_core_isolation_fix.sql
snowflake/007_cortex_agent.sql
snowflake/008_quantity_aware_scenarios.sql
```

They create the database, load deterministic reference data, define relational and semantic metrics, validate expected results, cut over to layered security zones, remove residual legacy grants, define the secure Cortex Agent, and upgrade the metric to quantity-aware scenario allocation.

Deploy only with authority to create persistent Snowflake objects and grants:

```bash
make snowflake-deploy
```

For an already deployed account, apply only the forward migration without replaying the seed loader:

```bash
make snowflake-upgrade
```

Run least-privilege validation:

```bash
make snowflake-validate
make snowflake-scorecard
make snowflake-parity
```

Start the API against Snowflake:

```bash
make backend-snowflake
```

`/health` reports repository mode, source system, connection name, snapshot metadata, and recent query IDs without exposing credentials.

## Snowflake-only hosting

The application deploys to Snowpark Container Services as two containers in one service instance:

- the public Next.js endpoint on port `3000`;
- an internal FastAPI container on port `8000`;
- same-origin `/api/*` proxying over the instance-local network;
- Snowflake-authenticated ingress identity for application authorization;
- a mounted, rotating service OAuth token for password-free database access;
- one `CPU_X64_XS` node, one service instance, and Linux/AMD64 images stored in Snowflake's image repository.

Install the official Snowflake CLI and start a Podman machine, then deploy:

```bash
make snowflake-host \
  PLANNER_USERS=SHINGLOO \
  APPROVER_USERS=SECOND_REVIEWER \
  PODMAN_MACHINE=zentro-podman
```

The deployer creates `APP.SUPPLYCHAIN_IMAGES` and `SUPPLYCHAIN_APP_POOL`, builds immutable API/web tags, updates the service specification, waits for both readiness probes, and returns the Snowflake ingress URL. `SUPPLYCHAIN_PLANNER_USERS` and `SUPPLYCHAIN_APPROVER_USERS` are server-side user mappings and must be non-empty, non-overlapping Snowflake usernames. Human users receive only `SUPPLYCHAIN_APP_READONLY` plus the endpoint's `UI_USAGE` service role never `SUPPLYCHAIN_APP_RUNTIME`. The service owner inherits the non-human runtime data role; its temporary `CREATE SERVICE` and `BIND SERVICE ENDPOINT` grants are revoked after deployment.

The web build is a Next.js static export served by an unprivileged AMD64 Nginx container. `/api/*` stays same-origin and is proxied to the colocated FastAPI container, including Snowflake's authenticated ingress identity header. This avoids shipping build-machine-native Node artifacts into the Snowflake runtime. The API readiness probe executes `SELECT 1`; if the session has closed, it re-reads the mounted Snowflake token and reconnects once before failing unhealthy.

Snowflake currently rejects service-level auto-suspend for a service with a public endpoint. The foundation uses the smallest available compute family and one node, but the public service consumes compute while running. Suspend it when the link is not needed:

```sql
ALTER SERVICE SUPPLYCHAIN_TRUST_GRAPH.APP.SUPPLYCHAIN_TRUST_GRAPH_SERVICE SUSPEND;
ALTER COMPUTE POOL SUPPLYCHAIN_APP_POOL SUSPEND;
```

Resume before a demonstration:

```sql
ALTER COMPUTE POOL SUPPLYCHAIN_APP_POOL RESUME;
ALTER SERVICE SUPPLYCHAIN_TRUST_GRAPH.APP.SUPPLYCHAIN_TRUST_GRAPH_SERVICE RESUME;
```

## Public no-login showcase

`streamlit_app.py` provides a separate public presentation boundary for viewers who do not have a Snowflake account. It is designed for Streamlit Community Cloud and connects directly to the same `GOVERNED` views with a dedicated key-pair service identity that holds only `SUPPLYCHAIN_APP_READONLY`.

The public surface supports:

- the supplier-to-customer blast radius;
- governed revenue, order, stockout, and delivery metrics;
- 3/7/14/21-day scenario comparison;
- deterministic conversational routing;
- source evidence downloads;
- approved-alternative ranking; and
- existing audit evidence.

It intentionally cannot insert a mitigation, approve a decision, change roles, execute generated SQL, or call an ERP system. “Prepare draft” creates a clearly labelled browser-session preview only. The authenticated SPCS application remains the authoritative planner → independent reviewer workflow.

Run it locally in governed fixture mode:

```bash
pip install -r requirements.txt
streamlit run streamlit_app.py
```

For a local live-data check, use an existing named Snowflake connection:

```bash
SNOWFLAKE_CONNECTION_NAME=supplychain-hackathon \
streamlit run streamlit_app.py
```

The deployed app reads these Streamlit secrets, configured in Community Cloud rather than committed to Git:

```toml
[snowflake]
account = "<organization-account>"
user = "SUPPLYCHAIN_STREAMLIT_SVC"
private_key = """-----BEGIN PRIVATE KEY-----
<private-key-material>
-----END PRIVATE KEY-----"""
role = "SUPPLYCHAIN_APP_READONLY"
warehouse = "COMPUTE_WH"
```

The connector rejects any externally supplied role other than `SUPPLYCHAIN_APP_READONLY`, disables secondary roles after connecting, and never logs secret values. `.streamlit/secrets.toml` is ignored by Git.

### Durable workflow verification

With the Snowflake-backed API running:

```bash
make live-api-verify
```

The probe creates a mitigation draft, proves owner self-approval is denied, records an independent approval, replays the idempotency key, and verifies audit uniqueness. It never calls an ERP system or creates a purchase order.

### Cortex Analyst verification

```bash
make coco-analyst-verify
make coco-analyst-eval
```

The full evaluation covers the golden metric, exact affected orders, and plant-level breakdown. It accepts only guarded read-only SQL, verifies exact results, and records attributable audit evidence.

## REST API

| Method | Route | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Repository mode, source, connection, and query health. |
| `GET` | `/api/session` | Resolve the current allowlisted identity and roles. |
| `GET` | `/api/demo` | Return the complete dashboard bundle. |
| `GET` | `/api/dashboard` | Return executive summary metrics. |
| `GET` | `/api/scenarios/compare` | Compare governed impact across delay assumptions. |
| `GET` | `/api/governed-metrics` | Return governed metric definitions and values. |
| `POST` | `/api/conversation` | Route a natural-language supply-chain question. |
| `POST` | `/api/workflows/supplier-delay` | Run a deterministic disruption investigation. |
| `GET` | `/api/inventory-risk` | Inspect part and plant inventory exposure. |
| `GET` | `/api/order-impact` | Trace affected orders and revenue. |
| `GET` | `/api/approved-alternatives` | List qualified mitigation suppliers. |
| `POST` | `/api/mitigations/draft` | Create a planner-owned draft. |
| `GET` | `/api/mitigations` | Load the role-protected durable approval inbox. |
| `POST` | `/api/mitigations/{action_id}/approve` | Record an independent approval. |
| `POST` | `/api/mitigations/{action_id}/return-for-revision` | Return a versioned draft. |
| `GET` | `/api/audit-events` | Read attributable append-only evidence. |

Example governed question:

```bash
curl -sS http://127.0.0.1:8000/api/conversation \
  -H 'Content-Type: application/json' \
  -d '{"question":"What revenue is at risk if SUP-042 is delayed by 14 days?"}'
```

Example deterministic workflow:

```bash
curl -sS http://127.0.0.1:8000/api/workflows/supplier-delay \
  -H 'Content-Type: application/json' \
  -d '{"supplier_id":"SUP-042","delay_days":14}'
```

## Verification

Run the complete local release gate:

```bash
make verify-submission
```

This runs the backend suite, production Next.js build, and JSON scorecard. Individual checks are also available:

```bash
make test
make build
make scorecard
```

Coverage includes exact quantity-aware metrics, safety stock, zero-risk behavior, scenario thresholds, lead-time-aware alternatives, metric parity, evidence classification, provenance, intent allowlisting, policy bypasses, MCP contracts, Snowflake ingress identity, server-derived ownership, multi-action approval inboxes, duplicate-draft conflicts, role authorization, separation of duties, actor-bound idempotency, approval-time revalidation, Snowflake transactions, append-only audit rules, layered grants, guarded generated SQL, semantic-view contracts, live dependency health/reconnect, hosting-role isolation, and portable Snowflake images. The current suite contains 52 backend tests plus frontend lint, standalone production build, and static-export build gates.

## Repository layout

```text
.
├── .cortex/skills/                 # Reusable CoCo workflows
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI REST adapter
│   │   ├── mcp_server.py           # Typed MCP tool surface
│   │   ├── service.py              # Deterministic workflow engine
│   │   ├── policy.py               # Identity, roles, and policy checks
│   │   ├── snowflake_repository.py # Governed Snowflake adapter
│   │   └── data.py                 # Fixture repository and data
│   └── tests/                      # Metric, policy, MCP, and contract tests
├── frontend/
│   ├── app/                        # Next.js App Router entry points
│   └── src/                        # Dashboard, types, and preview data
├── deploy/spcs/                    # Snowflake container images and service spec
├── scripts/                        # Deployment and verification harnesses
├── snowflake/                      # SQL migrations and ontology contract
├── ARCHITECTURE.md                 # Boundaries and runtime design
├── COCO_EVIDENCE.md                # Reproducible CoCo/Snowflake evidence
├── DEMO_SCRIPT.md                  # Guided product walkthrough
├── PROJECT_DECISIONS.md            # Design decisions and trade-offs
└── Makefile                        # Local and Snowflake workflows
```

## Failure behavior

The system prefers a visible refusal over an ungrounded success:

- missing source record → `INSUFFICIENT_EVIDENCE`;
- missing identifier or delay → `NEEDS_CLARIFICATION`;
- unsupported or bypass request → `REJECTED_BY_POLICY`;
- unapproved alternative → draft rejected;
- planner self-approval → authorization rejected;
- stale action version → reload-required conflict;
- repeated idempotency key → original decision returned without duplication;
- API unavailable in the UI → unverified preview and mutations disabled;
- Snowflake unavailable in live mode → the operation fails instead of silently changing data sources.

## Production hardening path

The governed decision path is implemented; production adoption should additionally:

- move hosted role membership from deployment-time allowlists to an organization-managed identity/entitlement source;
- replace deterministic seed loading with controlled CDC or batch ingestion;
- connect approved decisions to a separately authorized ERP execution service;
- integrate operational alerts with organization-owned channels;
- add organization-specific masking, retention, and row-access policies;
- configure observability, rate limits, retries, and production SLOs;
- use an eligible Snowflake account when native Cortex Agent invocation is required.

These changes do not require weakening the existing evidence, qualification, approval, transaction, or audit boundaries.

## Additional documentation

- [Architecture and trust boundaries](ARCHITECTURE.md)
- [Project decisions and trade-offs](PROJECT_DECISIONS.md)
- [CoCo CLI and Snowflake evidence](COCO_EVIDENCE.md)
- [Guided product walkthrough](DEMO_SCRIPT.md)
