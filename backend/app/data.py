from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import os
from threading import RLock
from typing import Any
from zoneinfo import ZoneInfo


FIXTURES: dict[str, list[dict[str, Any]]] = {
    "suppliers": [
        {"supplier_id": "SUP-042", "supplier_name": "NordWerk Components", "country": "Germany", "risk_tier": "Critical", "status": "ACTIVE"},
        {"supplier_id": "SUP-017", "supplier_name": "Axis Precision Works", "country": "India", "risk_tier": "Low", "status": "ACTIVE"},
        {"supplier_id": "SUP-018", "supplier_name": "VoltEdge Systems", "country": "Malaysia", "risk_tier": "Medium", "status": "ACTIVE"},
        {"supplier_id": "SUP-063", "supplier_name": "Kaveri Industrial Co.", "country": "India", "risk_tier": "Low", "status": "ACTIVE"},
        {"supplier_id": "SUP-031", "supplier_name": "RapidFab Trading", "country": "UAE", "risk_tier": "High", "status": "ACTIVE"},
    ],
    "parts": [
        {"part_id": "PRT-AX14", "part_name": "Precision bearing assembly", "category": "Drive systems"},
        {"part_id": "PRT-CTRL9", "part_name": "Motor control unit", "category": "Electronics"},
    ],
    "supplier_parts": [
        {"supplier_id": "SUP-042", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "approved": True, "lead_time_days": 12, "available_capacity": 650, "cost_band": "Baseline"},
        {"supplier_id": "SUP-042", "part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "approved": True, "lead_time_days": 14, "available_capacity": 220, "cost_band": "Baseline"},
        {"supplier_id": "SUP-017", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "approved": True, "lead_time_days": 5, "available_capacity": 500, "cost_band": "+8–11%"},
        {"supplier_id": "SUP-063", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "approved": True, "lead_time_days": 8, "available_capacity": 300, "cost_band": "+3–5%"},
        {"supplier_id": "SUP-018", "part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "approved": True, "lead_time_days": 7, "available_capacity": 200, "cost_band": "+12–15%"},
        {"supplier_id": "SUP-063", "part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "approved": True, "lead_time_days": 10, "available_capacity": 140, "cost_band": "+6–9%"},
        {"supplier_id": "SUP-031", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "approved": False, "lead_time_days": 3, "available_capacity": 800, "cost_band": "+2–4%"},
    ],
    "plants": [
        {"plant_id": "PLT-PUN", "plant_name": "Pune Assembly", "city": "Pune", "country": "India"},
        {"plant_id": "PLT-BLR", "plant_name": "Bengaluru Systems", "city": "Bengaluru", "country": "India"},
    ],
    "inventory": [
        {"part_id": "PRT-AX14", "plant_id": "PLT-PUN", "on_hand": 280, "safety_stock": 100, "daily_demand": 35, "snapshot_at": "2026-09-29T08:00:00+05:30"},
        {"part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "on_hand": 95, "safety_stock": 60, "daily_demand": 12, "snapshot_at": "2026-09-29T08:00:00+05:30"},
    ],
    "shipments": [
        {"shipment_id": "SHP-8801", "supplier_id": "SUP-042", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "quantity": 470, "promised_date": "2026-10-03", "status": "IN_TRANSIT", "source_system": "TMS", "updated_at": "2026-09-29T08:24:00+05:30"},
        {"shipment_id": "SHP-8802", "supplier_id": "SUP-042", "part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "quantity": 225, "promised_date": "2026-10-05", "status": "IN_TRANSIT", "source_system": "TMS", "updated_at": "2026-09-29T08:27:00+05:30"},
        {"shipment_id": "SHP-H001", "supplier_id": "SUP-017", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "quantity": 300, "promised_date": "2026-08-01", "received_date": "2026-07-31", "status": "RECEIVED", "source_system": "TMS"},
        {"shipment_id": "SHP-H002", "supplier_id": "SUP-042", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "quantity": 250, "promised_date": "2026-08-15", "received_date": "2026-08-18", "status": "RECEIVED", "source_system": "TMS"},
        {"shipment_id": "SHP-H003", "supplier_id": "SUP-018", "part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "quantity": 160, "promised_date": "2026-09-01", "received_date": "2026-09-01", "status": "RECEIVED", "source_system": "TMS"},
        {"shipment_id": "SHP-H004", "supplier_id": "SUP-063", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "quantity": 180, "promised_date": "2026-09-15", "received_date": "2026-09-13", "status": "RECEIVED", "source_system": "TMS"},
    ],
    "customers": [
        {"customer_id": "CUS-101", "customer_name": "Apex Mobility", "tier": "Strategic"},
        {"customer_id": "CUS-117", "customer_name": "Helios Industrial", "tier": "Strategic"},
        {"customer_id": "CUS-204", "customer_name": "Meridian Robotics", "tier": "Priority"},
        {"customer_id": "CUS-303", "customer_name": "Orion Equipment", "tier": "Standard"},
    ],
    "sales_orders": [
        {"order_id": "SO-7101", "customer_id": "CUS-101", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "required_date": "2026-10-08", "order_value": 240000, "quantity": 400, "status": "OPEN"},
        {"order_id": "SO-7102", "customer_id": "CUS-204", "part_id": "PRT-AX14", "plant_id": "PLT-PUN", "required_date": "2026-10-12", "order_value": 150000, "quantity": 250, "status": "OPEN"},
        {"order_id": "SO-7103", "customer_id": "CUS-117", "part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "required_date": "2026-10-10", "order_value": 196000, "quantity": 140, "status": "OPEN"},
        {"order_id": "SO-7104", "customer_id": "CUS-303", "part_id": "PRT-CTRL9", "plant_id": "PLT-BLR", "required_date": "2026-10-22", "order_value": 168000, "quantity": 120, "status": "OPEN"},
    ],
    "supplier_documents": [
        {"document_id": "DOC-042-09", "supplier_id": "SUP-042", "part_id": None, "document_type": "DELAY_NOTICE", "title": "Capacity incident notice", "detail": "Supplier confirmed a 14-day slip caused by heat-treatment line maintenance.", "observed_at": "2026-09-29T08:15:00+05:30", "source_system": "Supplier Portal"},
    ],
    "disruption_events": [
        {"disruption_id": "DIS-2026-009", "supplier_id": "SUP-042", "delay_days": 14, "reported_at": "2026-09-29T08:15:00+05:30", "status": "ACTIVE", "source_document_id": "DOC-042-09"},
    ],
}


class FixtureRepository:
    """Deterministic local source with mutable audit/action ledgers."""

    def __init__(self) -> None:
        self.mode = "fixture"
        self.source_system = "GOVERNED_FIXTURE_LAYER"
        self.connection_name: str | None = None
        self.last_query_ids: list[str] = []
        self.snapshot_loaded_at = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(
            timespec="seconds"
        )
        self._data = deepcopy(FIXTURES)
        self.mitigation_actions: list[dict[str, Any]] = []
        self.idempotency_results: dict[str, dict[str, Any]] = {}
        self.audit_events: list[dict[str, Any]] = [
            {
                "audit_id": "AUD-4BC812",
                "event_type": "DISRUPTION_RECEIVED",
                "actor": "Supplier Portal",
                "created_at": "2026-09-29T08:15:00+05:30",
                "summary": "Supplier delay notice registered and linked to two inbound shipments.",
                "correlation_id": "WF-7A41C2",
            }
        ]
        self.lock = RLock()

    def all(self, entity: str) -> list[dict[str, Any]]:
        return deepcopy(self._data.get(entity, []))

    def one(self, entity: str, key: str, value: Any) -> dict[str, Any] | None:
        return next((item for item in self.all(entity) if item.get(key) == value), None)

    def append_audit(self, event: dict[str, Any]) -> None:
        with self.lock:
            self.audit_events.insert(0, deepcopy(event))

    def refresh_workflow_state(self) -> None:
        """Refresh durable actions before list/decision operations.

        Fixture mode is already process-local and current.
        """

    def create_action_with_audit(
        self,
        action: dict[str, Any],
        event: dict[str, Any],
    ) -> None:
        with self.lock:
            self.mitigation_actions.append(deepcopy(action))
            self.audit_events.insert(0, deepcopy(event))

    def apply_decision_with_audit(
        self,
        action: dict[str, Any],
        event: dict[str, Any],
        cache_key: str | None,
        previous_version: int,
    ) -> None:
        del previous_version
        with self.lock:
            index = next(
                (
                    index
                    for index, item in enumerate(self.mitigation_actions)
                    if item["action_id"] == action["action_id"]
                ),
                None,
            )
            if index is None:
                raise LookupError(f"Mitigation action {action['action_id']} does not exist.")
            self.mitigation_actions[index] = deepcopy(action)
            self.audit_events.insert(0, deepcopy(event))
            if cache_key:
                self.idempotency_results[cache_key] = deepcopy(action)

    def status(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "source_system": self.source_system,
            "connection_name": self.connection_name,
            "last_query_ids": list(self.last_query_ids[-8:]),
            "snapshot_loaded_at": self.snapshot_loaded_at,
            "semantic_validation": {
                "status": "NOT_APPLICABLE",
                "reason": "Fixture mode has no live Snowflake semantic view.",
            },
            "database_zones": {
                "source": "GOVERNED_FIXTURE_LAYER",
                "analytics": "DETERMINISTIC_METRICS",
                "workflow": "IN_MEMORY_WORKFLOW",
                "audit": "IN_MEMORY_APPEND_ONLY_AUDIT",
            },
        }

    def health_check(self) -> dict[str, Any]:
        return {"database": "not_applicable", "connected": True}

    def close(self) -> None:
        """Release repository resources; fixture mode has none."""


def build_repository() -> FixtureRepository:
    mode = os.getenv("SUPPLYCHAIN_DATA_MODE", "fixture").strip().lower()
    if mode == "fixture":
        return FixtureRepository()
    if mode != "snowflake":
        raise RuntimeError("SUPPLYCHAIN_DATA_MODE must be either 'fixture' or 'snowflake'.")

    from .snowflake_repository import SnowflakeRepository

    token_path = os.getenv("SNOWFLAKE_TOKEN_PATH", "/snowflake/session/token")
    running_in_spcs = os.path.isfile(token_path)
    connection_name = os.getenv("SNOWFLAKE_CONNECTION_NAME", "supplychain-hackathon").strip()
    if not connection_name and not running_in_spcs:
        raise RuntimeError("SNOWFLAKE_CONNECTION_NAME is required in Snowflake mode.")
    return SnowflakeRepository(None if running_in_spcs else connection_name)


repository = build_repository()
