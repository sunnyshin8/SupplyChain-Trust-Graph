from app.data import FixtureRepository
from app.service import REVENUE_AT_RISK_DEFINITION, SupplyChainService


def make_service() -> SupplyChainService:
    return SupplyChainService(FixtureRepository())


def test_supplier_delay_calculates_governed_revenue_at_risk() -> None:
    result = make_service().analyze_supplier_delay("SUP-042", 14)

    assert result["risk_summary"]["revenue_at_risk"] == 586_000
    assert result["risk_summary"]["impacted_orders"] == 3
    assert {order["order_id"] for order in result["open_orders"]} == {
        "SO-7101",
        "SO-7102",
        "SO-7103",
    }
    assert result["metric_definition"] == REVENUE_AT_RISK_DEFINITION
    assert "SO-7104" not in {order["order_id"] for order in result["open_orders"]}


def test_zero_risk_scenario_has_truthful_narrative_and_provenance() -> None:
    service = make_service()
    result = service.analyze_supplier_delay("SUP-042", 3, record_audit=False)
    bundle = service.demo_bundle("SUP-042", 3)

    assert result["risk_summary"]["revenue_at_risk"] == 0
    assert result["risk_summary"]["severity"] == "LOW"
    assert "No open order fails" in result["risk_summary"]["narrative"]
    assert result["evidence"][-1]["source_system"] == (
        "Governed fixture + deterministic metric v1.0"
    )
    assert bundle["provenance"]["metric_engine"] == "DETERMINISTIC_PYTHON_V1"
    assert len(bundle["provenance"]["policy_checks"]) == 7


def test_on_time_delivery_and_stockout_metrics_are_deterministic() -> None:
    metrics = make_service().governed_metrics()

    assert metrics["on_time_delivery_rate"] == 0.75
    assert metrics["on_time_delivery_numerator"] == 3
    assert metrics["deliveries_due_denominator"] == 4
    assert metrics["plants_at_stockout_risk"] == 2


def test_inventory_risk_uses_protected_safety_stock() -> None:
    result = make_service().get_inventory_risk("PRT-AX14", "PLT-PUN")["inventory_risk"][0]

    assert result["available_inventory"] == 280
    assert result["safety_stock"] == 100
    assert result["allocatable_inventory"] == 180
    assert result["projected_shortage_date"] == "2026-10-05"
    assert result["lead_time_window_end"] == "2026-10-11"
    assert result["projected_demand_in_lead_time_window"] == 420
    assert result["confirmed_inbound_inside_window"] == 0
    assert result["is_stockout_risk"] is True
    assert result["risk_level"] == "CRITICAL"


def test_order_risk_uses_cumulative_allocation_by_required_date() -> None:
    repo = FixtureRepository()
    repo._data["sales_orders"] = [
        {
            "order_id": "SO-CUM-1",
            "customer_id": "CUS-101",
            "part_id": "PRT-AX14",
            "plant_id": "PLT-PUN",
            "required_date": "2026-10-08",
            "order_value": 100_000,
            "quantity": 100,
            "status": "OPEN",
        },
        {
            "order_id": "SO-CUM-2",
            "customer_id": "CUS-204",
            "part_id": "PRT-AX14",
            "plant_id": "PLT-PUN",
            "required_date": "2026-10-09",
            "order_value": 120_000,
            "quantity": 100,
            "status": "OPEN",
        },
    ]

    result = SupplyChainService(repo).trace_order_impact("PRT-AX14", 14)

    assert {item["order_id"] for item in result["protected_sales_orders"]} == {"SO-CUM-1"}
    assert {item["order_id"] for item in result["affected_sales_orders"]} == {"SO-CUM-2"}
    assert result["revenue_at_risk"] == 120_000


def test_on_time_inbound_must_have_enough_quantity_to_protect_an_order() -> None:
    repo = FixtureRepository()
    for shipment in repo._data["shipments"]:
        if shipment["shipment_id"] == "SHP-8801":
            shipment["quantity"] = 10

    result = SupplyChainService(repo).trace_order_impact(
        "PRT-AX14",
        1,
        "SUP-042",
    )

    assert result["affected_sales_orders"][0]["order_id"] == "SO-7101"
    assert result["affected_sales_orders"][0]["shortage_quantity"] == 210


def test_engine_supports_a_second_disrupted_supplier_without_self_recommendation() -> None:
    repo = FixtureRepository()
    repo._data["disruption_events"].append(
        {
            "disruption_id": "DIS-2026-018",
            "supplier_id": "SUP-018",
            "delay_days": 7,
            "reported_at": "2026-09-29T09:00:00+05:30",
            "status": "ACTIVE",
            "source_document_id": None,
        }
    )
    repo._data["shipments"].append(
        {
            "shipment_id": "SHP-1801",
            "supplier_id": "SUP-018",
            "part_id": "PRT-CTRL9",
            "plant_id": "PLT-BLR",
            "quantity": 225,
            "promised_date": "2026-10-06",
            "status": "IN_TRANSIT",
            "source_system": "TMS",
            "updated_at": "2026-09-29T09:00:00+05:30",
        }
    )
    service = SupplyChainService(repo)

    result = service.analyze_supplier_delay("SUP-018", 7, record_audit=False)
    alternatives = service.list_approved_alternatives(
        "PRT-CTRL9",
        "PLT-BLR",
        delay_days=7,
        disrupted_supplier_id="SUP-018",
    )

    assert result["supplier"]["supplier_id"] == "SUP-018"
    assert "SUP-018" not in {
        item["supplier_id"] for item in alternatives["approved_alternatives"]
    }


def test_scenario_comparison_and_evidence_provenance_are_explicit() -> None:
    service = make_service()

    comparison = service.compare_delay_scenarios("SUP-042", [3, 7, 14])
    analysis = service.analyze_supplier_delay("SUP-042", 14, record_audit=False)
    shipment_evidence = {
        item["reference_id"]: item
        for item in analysis["evidence"]
        if item["source_type"] == "Shipment scenario"
    }

    assert [item["revenue_at_risk"] for item in comparison["scenarios"]] == [
        0,
        436_000,
        586_000,
    ]
    assert comparison["first_exposure_delay_days"] == 7
    assert shipment_evidence["SHP-8801"]["observed_at"] == "2026-09-29T08:24:00+05:30"
    assert shipment_evidence["SHP-8801"]["evidence_status"] == "SCENARIO_PROJECTION"
