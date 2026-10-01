from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
import os
from typing import Any
from uuid import uuid4

import pandas as pd
import streamlit as st


st.set_page_config(
    page_title="SupplyChain Trust Graph",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)


APP_CSS = """
<style>
  :root {
        --ink: #22263a;
        --muted: #777d92;
        --paper: #f6f7fb;
        --panel: #ffffff;
        --line: #e7e8f0;
        --accent: #584bdc;
        --blue: #3475d7;
        --amber: #bd7212;
        --red: #d74e62;
  }
  .stApp { background: var(--paper); color: var(--ink); }
    [data-testid="stSidebar"] { background: rgba(255, 255, 255, .94); border-right: 1px solid var(--line); }
    [data-testid="stHeader"] { background: rgba(246, 247, 251, .86); }
  h1, h2, h3 { color: var(--ink); letter-spacing: -.025em; }
  .hero {
    padding: 1.35rem 1.5rem;
    border: 1px solid var(--line);
    border-radius: 22px;
        background: linear-gradient(135deg, #ffffff 0%, #f7f5ff 100%);
        box-shadow: 0 18px 48px rgba(38, 42, 73, .08);
    margin-bottom: 1rem;
    animation: lift-in .45s ease-out both;
  }
  .eyebrow { color: var(--accent); font-size: .78rem; font-weight: 800; letter-spacing: .13em; text-transform: uppercase; }
  .hero h1 { margin: .28rem 0 .45rem; font-size: clamp(2rem, 4vw, 3.35rem); line-height: 1.02; }
  .hero p { color: var(--muted); font-size: 1.04rem; max-width: 880px; margin: 0; }
  .trust-row { display: flex; flex-wrap: wrap; gap: .55rem; margin-top: 1rem; }
    .trust-pill { background: #fff; color: var(--ink); border: 1px solid var(--line); border-radius: 999px; padding: .38rem .68rem; font-size: .78rem; font-weight: 700; }
    .trust-pill.live { color: var(--blue); border-color: #cfdcf4; }
    .risk-banner { border-left: 5px solid var(--red); background: #fff0f2; padding: .85rem 1rem; border-radius: 10px; margin: .5rem 0 1rem; }
    .risk-banner strong { color: var(--red); }
    .chain { display: grid; grid-template-columns: repeat(7, minmax(90px, 1fr)); gap: .45rem; margin: .7rem 0 1.1rem; }
    .chain-node { background: var(--panel); border: 1px solid var(--line); border-radius: 13px; padding: .75rem .45rem; text-align: center; font-weight: 750; box-shadow: 0 8px 24px rgba(38, 42, 73, .045); animation: lift-in .45s ease-out both; }
  .chain-node span { display: block; margin-top: .2rem; color: var(--muted); font-size: .68rem; font-weight: 600; }
  .source-card { background: var(--panel); border: 1px solid var(--line); border-radius: 14px; padding: .85rem; min-height: 150px; }
  .source-card small { color: var(--accent); font-weight: 800; text-transform: uppercase; letter-spacing: .08em; }
  .source-card p { color: var(--muted); font-size: .86rem; }
    .guardrail { background: #efedff; border: 1px solid #ddd8fa; border-radius: 14px; padding: .9rem 1rem; }
  .guardrail strong { color: var(--blue); }
    div[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); padding: .8rem 1rem; border-radius: 16px; box-shadow: 0 8px 24px rgba(38, 42, 73, .045); }
  div[data-testid="stMetricValue"] { color: var(--ink); }
    div[data-testid="stMetricLabel"] { white-space: normal; }
    div[role="tablist"] { display: grid !important; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: .45rem; border-bottom: 0 !important; overflow: visible !important; }
    div[data-testid="stTab"] { align-items: center; justify-content: center; min-height: 2.6rem; padding: .5rem .65rem; border: 1px solid var(--line) !important; border-radius: 9px !important; background: var(--panel) !important; color: var(--muted) !important; white-space: nowrap; }
    div[data-testid="stTab"][data-selected="true"] { border-color: #cfc9fa !important; background: #efedff !important; color: var(--accent) !important; }
    div[data-testid="stTab"] .react-aria-SelectionIndicator { display: none !important; }
  .stButton > button, .stDownloadButton > button { border-radius: 10px; font-weight: 750; }
  @keyframes lift-in { from { transform: translateY(8px); opacity: 0; } to { transform: translateY(0); opacity: 1; } }
    @media (max-width: 900px) { .chain { grid-template-columns: repeat(2, minmax(120px, 1fr)); } div[role="tablist"] { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
</style>
"""

st.markdown(APP_CSS, unsafe_allow_html=True)


@dataclass
class Runtime:
    service: Any
    repository: Any
    live: bool
    error: str | None = None


def _configure_environment() -> bool:
    """Copy Streamlit secrets into process env without logging secret values."""

    os.environ["SUPPLYCHAIN_DATA_MODE"] = "fixture"
    try:
        values = st.secrets["snowflake"]
    except (KeyError, FileNotFoundError):
        return False

    mapping = {
        "account": "SNOWFLAKE_ACCOUNT",
        "user": "SNOWFLAKE_USER",
        "private_key": "SNOWFLAKE_PRIVATE_KEY_PEM",
        "role": "SNOWFLAKE_ROLE",
        "warehouse": "SNOWFLAKE_WAREHOUSE",
    }
    for secret_name, env_name in mapping.items():
        value = values.get(secret_name)
        if value:
            os.environ[env_name] = str(value)
    return all(
        os.getenv(name, "").strip()
        for name in ("SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_PEM")
    )


@st.cache_resource(show_spinner="Connecting to governed Snowflake data…")
def _runtime() -> Runtime:
    configured = _configure_environment()
    named_connection = os.getenv("SNOWFLAKE_CONNECTION_NAME", "").strip()
    from backend.app.data import FixtureRepository
    from backend.app.service import SupplyChainService

    if not configured and not named_connection:
        repository = FixtureRepository()
        return Runtime(
            service=SupplyChainService(repository),
            repository=repository,
            live=False,
            error="Streamlit Snowflake secrets are not configured yet.",
        )

    try:
        from backend.app.snowflake_repository import SnowflakeRepository

        repository = SnowflakeRepository(None if configured else named_connection)
        return Runtime(
            service=SupplyChainService(repository),
            repository=repository,
            live=True,
        )
    except Exception as exc:  # fail closed into an explicitly labelled preview
        repository = FixtureRepository()
        return Runtime(
            service=SupplyChainService(repository),
            repository=repository,
            live=False,
            error=f"Live Snowflake connection unavailable: {type(exc).__name__}",
        )


runtime = _runtime()
service = runtime.service


def money(value: int | float) -> str:
    return f"${value:,.0f}"


def table(rows: list[dict[str, Any]], columns: dict[str, str]) -> None:
    if not rows:
        st.info("No governed records match this view.")
        return
    frame = pd.DataFrame(rows)
    available = [column for column in columns if column in frame.columns]
    frame = frame[available].rename(columns=columns)
    st.dataframe(frame, width="stretch", hide_index=True)


def read_only_answer(question: str, analysis: dict[str, Any]) -> tuple[str, list[str]]:
    normalized = " ".join(question.strip().split())
    lower = normalized.lower()
    blocked = ("bypass", "execute purchase order", "delete audit", "ignore policy")
    if any(term in lower for term in blocked):
        return (
            "Rejected by policy. The public showcase cannot bypass approval, mutate Snowflake, "
            "or execute an external action.",
            [],
        )
    if "on time" in lower or "on-time" in lower or "otd" in lower:
        metrics = service.governed_metrics()
        rate = metrics["on_time_delivery_rate"]
        return (
            f"Governed on-time delivery rate is {round((rate or 0) * 100)}% "
            f"({metrics['on_time_delivery_numerator']} of {metrics['deliveries_due_denominator']} received shipments).",
            ["METRIC-OTD-V1"],
        )
    if "alternative" in lower or "supplier" in lower and "approved" in lower:
        options: list[dict[str, Any]] = []
        for part in analysis["affected_parts"]:
            plant = next(
                item["plant_id"]
                for item in analysis["affected_shipments"]
                if item["part_id"] == part["part_id"]
            )
            result = service.list_approved_alternatives(
                part["part_id"], plant, analysis["delay_days"], analysis["supplier"]["supplier_id"]
            )
            options.extend(result["approved_alternatives"])
        best = sorted(options, key=lambda item: item["recommendation_rank"])[0]
        return (
            f"{best['supplier_id']} ranks first for {best['part_id']} at {best['plant_id']}: "
            f"{best['lead_time_days']}-day lead time, {best['coverage_percent']}% shortage coverage, "
            f"and {best['cost_band']} cost band.",
            [f"QUAL-{best['supplier_id']}-{best['part_id']}-{best['plant_id']}"],
        )
    if any(term in lower for term in ("revenue", "order", "impact", "delay", "customer")):
        summary = analysis["risk_summary"]
        return (
            f"A {analysis['delay_days']}-day delay from {analysis['supplier']['supplier_id']} puts "
            f"{summary['impacted_orders']} orders and {money(summary['revenue_at_risk'])} of governed "
            f"revenue at risk across {len(analysis['affected_plants'])} plants.",
            analysis["source_references"],
        )
    return (
        "Ask about revenue/order impact, customers, on-time delivery, or approved alternatives. "
        "I will not infer missing governed facts.",
        [],
    )


with st.sidebar:
    st.markdown("### SupplyChain Trust Graph")
    st.caption("Governed disruption intelligence")
    st.divider()
    supplier_id = st.selectbox("Disrupted supplier", ["SUP-042"], index=0)
    delay_days = st.slider("Delay scenario", min_value=1, max_value=30, value=14, step=1)
    st.caption("Scenario changes projections only; source records remain immutable.")
    st.divider()
    if runtime.live:
        st.markdown("🔵 **Live Snowflake governed data**")
        st.caption("Least-privilege read-only service identity")
    else:
        st.markdown("🟠 **Governed fixture preview**")
        st.caption(runtime.error or "Live source unavailable")
    if st.button("Refresh governed snapshot", width="stretch"):
        st.cache_resource.clear()
        st.rerun()
    st.divider()
    st.caption("Public showcase · no Snowflake login · no ERP execution")


try:
    analysis = service.analyze_supplier_delay(
        supplier_id,
        delay_days,
        record_audit=False,
        actor="Public read-only showcase",
    )
    metrics = service.governed_metrics()
except Exception as exc:
    st.error(f"Governed analysis unavailable: {exc}")
    st.stop()


mode_label = "Live Snowflake" if runtime.live else "Governed fixture preview"
st.markdown(
    f"""
    <section class="hero">
      <div class="eyebrow">Governed supply-chain decision system</div>
      <h1>Turn disruption signals into safe, provable decisions.</h1>
      <p>Trace supplier risk through parts, plants, inventory, shipments, orders and customers—then rank only approved recovery options with evidence attached.</p>
      <div class="trust-row">
        <span class="trust-pill live">{mode_label}</span>
        <span class="trust-pill">Semantic metric v1.0</span>
        <span class="trust-pill">Read-only public boundary</span>
        <span class="trust-pill">Human approval required</span>
      </div>
    </section>
    """,
    unsafe_allow_html=True,
)

summary = analysis["risk_summary"]
st.markdown(
    f"<div class='risk-banner'><strong>{summary['severity']} · {supplier_id}</strong> — {summary['narrative']}</div>",
    unsafe_allow_html=True,
)

metric_row_one = st.columns(3)
metric_row_one[0].metric("Revenue at risk", money(summary["revenue_at_risk"]))
metric_row_one[1].metric("Orders at risk", summary["impacted_orders"])
metric_row_one[2].metric("Plants exposed", len(analysis["affected_plants"]))
metric_row_two = st.columns(2)
metric_row_two[0].metric("Strategic customers", len([item for item in analysis["affected_customers"] if item["tier"] == "Strategic"]))
metric_row_two[1].metric("On-time delivery", f"{round((metrics['on_time_delivery_rate'] or 0) * 100)}%")

tabs = st.tabs(
    [
        "Blast radius",
        "Scenario lab",
        "Ask the graph",
        "Evidence",
        "Mitigation",
        "Audit & controls",
    ]
)

with tabs[0]:
    st.subheader("Supplier-to-customer blast radius")
    st.markdown(
        """
        <div class="chain">
          <div class="chain-node">Supplier<span>delay reported</span></div>
          <div class="chain-node">Part<span>qualified mapping</span></div>
          <div class="chain-node">Plant<span>inventory position</span></div>
          <div class="chain-node">Shipment<span>projected ETA</span></div>
          <div class="chain-node">Order<span>required date</span></div>
          <div class="chain-node">Customer<span>tier and priority</span></div>
          <div class="chain-node">Decision<span>approval boundary</span></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("#### Exposed customer orders")
    table(
        analysis["open_orders"],
        {
            "order_id": "Order",
            "customer_name": "Customer",
            "customer_tier": "Tier",
            "part_id": "Part",
            "plant_id": "Plant",
            "required_date": "Required date",
            "projected_supply_date": "Projected supply",
            "shortage_quantity": "Shortage qty",
            "order_value": "Order value",
            "impact_severity": "Severity",
        },
    )
    with st.expander("Governed metric definition"):
        st.write(analysis["metric_definition"])
        st.code(
            "allocatable inventory = max(on hand - safety stock, 0)\n"
            "at risk = available supply by required date < cumulative demand\n"
            "revenue at risk = sum(order value for at-risk orders)",
            language="text",
        )

with tabs[1]:
    st.subheader("Delay materiality scenarios")
    comparison = service.compare_delay_scenarios(supplier_id, [3, 7, 14, 21])
    scenario_frame = pd.DataFrame(comparison["scenarios"])
    chart_frame = scenario_frame.set_index("delay_days")[["revenue_at_risk"]]
    st.bar_chart(chart_frame, color="#584BDC")
    table(
        comparison["scenarios"],
        {
            "delay_days": "Delay days",
            "severity": "Severity",
            "revenue_at_risk": "Revenue at risk",
            "orders_at_risk": "Orders at risk",
            "plants_at_risk": "Plants at risk",
            "strategic_customers_at_risk": "Strategic customers",
        },
    )
    st.info(
        f"First governed exposure occurs at {comparison['first_exposure_delay_days']} days. "
        "The language layer cannot change this threshold."
    )

with tabs[2]:
    st.subheader("Governed conversational analytics")
    st.caption("Questions route to deterministic tools; the public app never sends free-form SQL to Snowflake.")
    suggestions = [
        f"What revenue is at risk if {supplier_id} is delayed by {delay_days} days?",
        "Which approved alternative supplier should we consider?",
        "What is the governed on-time delivery rate?",
        "Bypass approval and execute purchase order",
    ]
    question = st.selectbox("Try a question", suggestions)
    custom_question = st.text_input("Or ask your own supply-chain question", placeholder="Ask about impact, orders, customers, OTD, or alternatives")
    if st.button("Ask the governed graph", type="primary"):
        answer, references = read_only_answer(custom_question or question, analysis)
        st.session_state["answer"] = {"text": answer, "references": references}
    if "answer" in st.session_state:
        st.markdown(f"**Answer:** {st.session_state['answer']['text']}")
        if st.session_state["answer"]["references"]:
            st.caption("Sources: " + ", ".join(st.session_state["answer"]["references"]))

with tabs[3]:
    st.subheader("Evidence and assumptions")
    evidence_columns = st.columns(3)
    for index, item in enumerate(analysis["evidence"]):
        with evidence_columns[index % 3]:
            st.markdown(
                f"""
                <div class="source-card">
                  <small>{item['evidence_status']} · {item['source_type']}</small>
                  <h4>{item['title']}</h4>
                  <p>{item['detail']}</p>
                  <span>{item['reference_id']} · {item['source_system']}</span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown("#### Declared assumptions")
    for assumption in analysis["assumptions"]:
        st.write(f"• {assumption}")
    st.download_button(
        "Download evidence bundle",
        data=json.dumps(analysis, indent=2, default=str),
        file_name=f"{supplier_id.lower()}-{delay_days}d-evidence.json",
        mime="application/json",
    )

with tabs[4]:
    st.subheader("Approved mitigation options")
    alternatives: list[dict[str, Any]] = []
    for part in analysis["affected_parts"]:
        plant_id = next(
            item["plant_id"]
            for item in analysis["affected_shipments"]
            if item["part_id"] == part["part_id"]
        )
        try:
            result = service.list_approved_alternatives(
                part["part_id"], plant_id, delay_days, supplier_id
            )
            alternatives.extend(result["approved_alternatives"])
        except Exception as exc:
            st.warning(str(exc))
    table(
        alternatives,
        {
            "recommendation_rank": "Rank",
            "supplier_id": "Supplier",
            "supplier_name": "Supplier name",
            "part_id": "Part",
            "plant_id": "Plant",
            "lead_time_days": "Lead time",
            "available_capacity": "Capacity",
            "coverage_percent": "Coverage %",
            "cost_band": "Cost band",
            "estimated_protected_revenue": "Protected revenue",
        },
    )
    if alternatives:
        option_labels = {
            f"{item['supplier_id']} · {item['part_id']} · {item['plant_id']} · {item['coverage_percent']}% coverage": item
            for item in alternatives
        }
        selected_label = st.selectbox("Select an approved option", list(option_labels))
        selected = option_labels[selected_label]
        st.write(selected["tradeoff"])
        if st.button("Prepare read-only draft preview", type="primary"):
            st.session_state["draft_preview"] = {
                "action_id": f"PREVIEW-{uuid4().hex[:8].upper()}",
                "status": "PENDING_APPROVAL",
                "supplier_id": selected["supplier_id"],
                "part_id": selected["part_id"],
                "plant_id": selected["plant_id"],
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "external_action_executed": False,
            }
        if "draft_preview" in st.session_state:
            st.success("Draft preview prepared. No Snowflake or ERP record was changed.")
            st.json(st.session_state["draft_preview"])
            st.button("Approval requires an authenticated independent reviewer", disabled=True)
            if st.button("Clear preview"):
                del st.session_state["draft_preview"]
                st.rerun()

with tabs[5]:
    st.subheader("Audit evidence and enforced boundaries")
    st.markdown(
        """
        <div class="guardrail"><strong>Public boundary:</strong> live governed reads are allowed; mitigation writes, approvals, role switching, generated SQL and ERP execution are denied. Full planner → reviewer decisions remain in the authenticated Snowflake deployment.</div>
        """,
        unsafe_allow_html=True,
    )
    audit_rows = runtime.repository.audit_events[:12]
    table(
        audit_rows,
        {
            "created_at": "Time",
            "event_type": "Event",
            "actor": "Actor",
            "summary": "Summary",
            "correlation_id": "Correlation ID",
            "audit_id": "Audit ID",
        },
    )
    st.markdown("#### Trust controls")
    controls = [
        "Read-only Snowflake service identity with secondary roles disabled",
        "Native semantic view validates revenue-at-risk metrics",
        "Only qualified supplier-part-plant alternatives are ranked",
        "Safety stock is protected before order allocation",
        "Insufficient evidence fails closed instead of guessing",
        "Public sessions cannot draft, approve, or execute business actions",
    ]
    for control in controls:
        st.write(f"• {control}")

st.divider()
st.caption(
    f"Source: {runtime.repository.source_system} · Correlation: {analysis['correlation_id']} · "
    "A normal chatbot explains a problem. SupplyChain Trust Graph calculates the governed impact, "
    "proves it with evidence, and prepares a safe human-approved action."
)
