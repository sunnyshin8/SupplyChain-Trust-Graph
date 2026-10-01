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
    --ink: #1f2335;
    --ink-2: #3a3f55;
    --muted: #6b7085;
    --paper: #f5f6fa;
    --panel: #ffffff;
    --panel-2: #fafbfd;
    --line: #e4e6ee;
    --line-strong: #d4d7e3;
    --accent: #5145d6;
    --accent-soft: #eeecfd;
    --accent-line: #d6d1fa;
    --blue: #2f6fd0;
    --amber: #b06a10;
    --red: #cf4459;
    --red-soft: #fdf1f3;
    --radius: 8px;
    --radius-sm: 6px;
    --shadow: 0 1px 2px rgba(31, 35, 53, .05);
  }
  .stApp { background: var(--paper); color: var(--ink); }
  [data-testid="stHeader"] { background: rgba(245, 246, 250, .88); backdrop-filter: blur(6px); border-bottom: 1px solid transparent; }
  .block-container, [data-testid="stMainBlockContainer"] { max-width: 1240px; padding: 2.75rem 2rem 3rem; margin: 0 auto; }
  h1, h2, h3, h4 { color: var(--ink); letter-spacing: -.015em; }
  h2, h3 { font-size: 1.12rem !important; font-weight: 650 !important; margin: .25rem 0 .5rem !important; padding: 0 !important; }
  [data-testid="stCaptionContainer"], .stCaption { color: var(--muted) !important; font-size: .8rem; }
  hr { margin: .9rem 0 !important; border-color: var(--line) !important; }
  [data-testid="stSidebar"] { background: var(--panel); border-right: 1px solid var(--line); }
  [data-testid="stSidebar"] [data-testid="stSidebarContent"] { padding-top: .25rem; }
  [data-testid="stSidebar"] [data-testid="stSidebarUserContent"] { padding: 1rem 1.1rem 1.5rem; }
  [data-testid="stSidebar"] h3 { font-size: 1rem !important; font-weight: 700 !important; margin: 0 0 .1rem !important; }
  [data-testid="stSidebar"] label, [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: var(--ink-2); font-size: .8rem !important; font-weight: 600; }
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { font-size: .86rem; line-height: 1.45; }
  [data-testid="stSidebar"] [data-baseweb="select"] > div { border-radius: var(--radius-sm); border-color: var(--line-strong); background: var(--panel-2); min-height: 2.25rem; }
  .hero { padding: 1.1rem 1.25rem; border: 1px solid var(--line); border-radius: var(--radius); background: var(--panel); box-shadow: var(--shadow); margin-bottom: .75rem; border-top: 3px solid var(--accent); }
  .eyebrow { color: var(--accent); font-size: .7rem; font-weight: 700; letter-spacing: .1em; text-transform: uppercase; }
  .hero h1 { margin: .3rem 0 .35rem; padding: 0; font-size: clamp(1.4rem, 2.4vw, 1.9rem); font-weight: 700; line-height: 1.18; letter-spacing: -.02em; }
  .hero p { color: var(--muted); font-size: .92rem; line-height: 1.5; max-width: 820px; margin: 0; }
  .trust-row { display: flex; flex-wrap: wrap; gap: .35rem; margin-top: .8rem; }
  .trust-pill { background: var(--panel-2); color: var(--ink-2); border: 1px solid var(--line); border-radius: var(--radius-sm); padding: .2rem .5rem; font-size: .72rem; font-weight: 600; line-height: 1.4; }
  .trust-pill.live { color: var(--blue); background: #f0f5fd; border-color: #cddcf3; }
  .risk-banner { border: 1px solid #f3d3d9; border-left: 3px solid var(--red); background: var(--red-soft); padding: .65rem .9rem; border-radius: var(--radius); margin: 0 0 .75rem; font-size: .88rem; line-height: 1.5; color: var(--ink-2); }
  .risk-banner strong { color: var(--red); font-weight: 700; }
  div[data-testid="stHorizontalBlock"] { gap: .75rem; }
  div[data-testid="stMetric"] { background: var(--panel); border: 1px solid var(--line); padding: .7rem .9rem; border-radius: var(--radius); box-shadow: var(--shadow); min-height: 100%; }
  div[data-testid="stMetricLabel"] { white-space: normal; }
  div[data-testid="stMetricLabel"] p { color: var(--muted); font-size: .72rem !important; font-weight: 600; letter-spacing: .04em; text-transform: uppercase; }
  div[data-testid="stMetricValue"] { color: var(--ink); font-size: 1.55rem !important; font-weight: 650; line-height: 1.2; font-variant-numeric: tabular-nums; }
  [data-testid="stTabs"] { margin-top: .5rem; }
  [data-testid="stTabs"] [role="tablist"], div[data-baseweb="tab-list"] { display: flex !important; flex-wrap: nowrap !important; grid-template-columns: none !important; gap: .2rem; width: 100%; overflow-x: auto !important; overflow-y: hidden !important; padding: .25rem; background: var(--panel); border: 1px solid var(--line) !important; border-radius: var(--radius); box-shadow: var(--shadow); scroll-behavior: smooth; scroll-snap-type: x proximity; overscroll-behavior-x: contain; -webkit-overflow-scrolling: touch; scrollbar-width: thin; scrollbar-color: transparent transparent; }
  [data-testid="stTabs"] [role="tablist"]:hover, div[data-baseweb="tab-list"]:hover { scrollbar-color: var(--line-strong) transparent; }
  [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { height: 4px; }
  [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar-track { background: transparent; }
  [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar-thumb { background: transparent; border-radius: 4px; }
  [data-testid="stTabs"] [role="tablist"]:hover::-webkit-scrollbar-thumb { background: var(--line-strong); }
  [data-testid="stTabs"] [role="tab"], div[data-testid="stTab"], button[data-baseweb="tab"] { flex: 0 0 auto !important; display: inline-flex; align-items: center; justify-content: center; min-height: 2.1rem; height: auto; margin: 0 !important; padding: .4rem .8rem !important; border: 0 !important; border-radius: var(--radius-sm) !important; background: transparent !important; color: var(--muted) !important; font-size: .84rem; font-weight: 600; white-space: nowrap; scroll-snap-align: start; transition: background .12s ease, color .12s ease; }
  [data-testid="stTabs"] [role="tab"] p { font-size: inherit !important; font-weight: inherit; margin: 0; white-space: nowrap; }
  [data-testid="stTabs"] [role="tab"]:hover { background: var(--paper) !important; color: var(--ink) !important; }
  [data-testid="stTabs"] [role="tab"][aria-selected="true"], div[data-testid="stTab"][data-selected="true"] { background: var(--accent-soft) !important; color: var(--accent) !important; box-shadow: inset 0 0 0 1px var(--accent-line); }
  [data-testid="stTabs"] [role="tab"]:focus-visible { outline: 2px solid var(--accent); outline-offset: -2px; }
  [data-testid="stTabs"] .react-aria-SelectionIndicator, div[data-baseweb="tab-highlight"], div[data-baseweb="tab-border"] { display: none !important; }
  [data-testid="stTabs"] [role="tablist"] > button:not([role="tab"]), [data-testid="stTabs"] [aria-label*="scroll" i] { display: none !important; }
  [data-testid="stTabs"] [role="tabpanel"], div[data-baseweb="tab-panel"] { padding-top: 1rem; }
  .chain { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: .4rem; margin: .5rem 0 1rem; }
  .chain-node { position: relative; background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: .6rem .5rem; text-align: center; font-size: .85rem; font-weight: 650; color: var(--ink); box-shadow: var(--shadow); }
  .chain-node:last-child { border-color: var(--accent-line); background: var(--accent-soft); color: var(--accent); }
  .chain-node span { display: block; margin-top: .15rem; color: var(--muted); font-size: .68rem; font-weight: 500; }
  .source-card { background: var(--panel); border: 1px solid var(--line); border-radius: var(--radius); padding: .8rem .9rem; min-height: 140px; box-shadow: var(--shadow); }
  .source-card small { color: var(--accent); font-size: .68rem; font-weight: 700; text-transform: uppercase; letter-spacing: .08em; }
  .source-card p { color: var(--muted); font-size: .84rem; line-height: 1.5; margin: .35rem 0 0; }
  .guardrail { background: var(--accent-soft); border: 1px solid var(--accent-line); border-radius: var(--radius); padding: .75rem .9rem; font-size: .86rem; line-height: 1.5; color: var(--ink-2); }
  .guardrail strong { color: var(--accent); }
  .stButton > button, .stDownloadButton > button { border-radius: var(--radius-sm); font-size: .85rem; font-weight: 600; min-height: 2.25rem; padding: .35rem .9rem; border-color: var(--line-strong); box-shadow: var(--shadow); }
  .stButton > button[kind="primary"] { background: var(--accent); border-color: var(--accent); }
  .stButton > button[kind="primary"]:hover { background: #463bc4; border-color: #463bc4; }
  [data-testid="stDataFrame"], [data-testid="stTable"] { border: 1px solid var(--line); border-radius: var(--radius); overflow: hidden; background: var(--panel); }
  [data-testid="stExpander"] details { border: 1px solid var(--line); border-radius: var(--radius); background: var(--panel); }
  [data-testid="stExpander"] summary p { font-size: .86rem; font-weight: 600; }
  [data-testid="stAlert"] { border-radius: var(--radius); }
  [data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { border-radius: var(--radius-sm); }
  @media (max-width: 1024px) {
    .chain { grid-template-columns: repeat(4, minmax(0, 1fr)); }
  }
  @media (max-width: 640px) {
    .block-container, [data-testid="stMainBlockContainer"] { padding: 3.25rem .85rem 2rem; }
    .hero { padding: .9rem 1rem; }
    .hero h1 { font-size: 1.3rem; }
    .hero p { font-size: .86rem; }
    div[data-testid="stMetric"] { padding: .6rem .75rem; }
    div[data-testid="stMetricValue"] { font-size: 1.3rem !important; }
    .chain { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    [data-testid="stTabs"] [role="tablist"], div[data-baseweb="tab-list"] { margin: 0 -.85rem; width: calc(100% + 1.7rem); border-radius: 0; border-left: 0 !important; border-right: 0 !important; padding: .25rem .6rem; scroll-padding-inline: .6rem; }
    [data-testid="stTabs"] [role="tab"], div[data-testid="stTab"], button[data-baseweb="tab"] { padding: .35rem .7rem !important; font-size: .8rem; min-height: 2rem; }
  }
  @media (hover: none) {
    [data-testid="stTabs"] [role="tablist"], div[data-baseweb="tab-list"] { scrollbar-width: none; }
    [data-testid="stTabs"] [role="tablist"]::-webkit-scrollbar { display: none; }
  }
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
