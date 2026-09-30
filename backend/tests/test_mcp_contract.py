import asyncio

from app.mcp_server import mcp


EXPECTED_TOOLS = {
    "ask_supply_chain",
    "analyze_supplier_delay",
    "get_inventory_risk",
    "trace_order_impact",
    "list_approved_alternatives",
    "draft_mitigation",
}


def test_mcp_tool_surface_and_required_schemas() -> None:
    tools = asyncio.run(mcp.list_tools())
    by_name = {tool.name: tool for tool in tools}

    assert set(by_name) == EXPECTED_TOOLS
    assert by_name["ask_supply_chain"].inputSchema["required"] == ["question"]
    assert set(by_name["analyze_supplier_delay"].inputSchema["required"]) == {
        "supplier_id",
        "delay_days",
    }
    assert set(by_name["draft_mitigation"].inputSchema["required"]) == {
        "disruption_context",
        "selected_mitigation_option",
    }
    assert "owner" not in by_name["draft_mitigation"].inputSchema["properties"]


def test_mcp_natural_language_tool_returns_structured_grounded_output() -> None:
    content, payload = asyncio.run(
        mcp.call_tool(
            "ask_supply_chain",
            {"question": "What revenue is at risk if SUP-042 is delayed by 14 days?"},
        )
    )

    assert content[0].type == "text"
    assert payload["status"] == "ANSWERED"
    assert payload["answer_policy"] == "DETERMINISTIC_TOOLS_ONLY"
    assert "METRIC-RAR-V1" in payload["source_references"]
