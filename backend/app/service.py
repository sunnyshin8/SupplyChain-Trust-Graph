from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
from math import floor
import re
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

from .data import FixtureRepository, repository
from .models import DisruptionContext, MitigationAction, MitigationOption


REVENUE_AT_RISK_DEFINITION = (
    "Sum of affected open-order value where the required part cannot arrive "
    "before the customer-required date. Safety stock is protected."
)


class EvidenceError(LookupError):
    """Raised when governed data is not sufficient to answer safely."""


class GovernanceConflictError(ValueError):
    """Raised when workflow state changed or conflicts with an active action."""


class GovernanceAuthorizationError(PermissionError):
    """Raised when an authenticated actor violates a workflow authorization rule."""


def _now() -> str:
    return datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(timespec="seconds")


def _id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:8].upper()}"


def _parse_date(value: str) -> date:
    return date.fromisoformat(value[:10])


class SupplyChainService:
    """Internal workflow engine for analysis, recommendation, and approvals."""

    def __init__(self, repo: FixtureRepository | None = None) -> None:
        self.repo = repo or repository

    def _audit(
        self,
        event_type: str,
        actor: str,
        summary: str,
        correlation_id: str,
        *,
        audit_id: str | None = None,
        entity_type: str = "WORKFLOW",
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        event = {
            "audit_id": audit_id or _id("AUD"),
            "event_type": event_type,
            "actor": actor,
            "created_at": _now(),
            "summary": summary,
            "correlation_id": correlation_id,
            "entity_type": entity_type,
            "entity_id": entity_id or correlation_id,
        }
        self.repo.append_audit(event)
        return event

    def _audit_event(
        self,
        event_type: str,
        actor: str,
        summary: str,
        correlation_id: str,
        *,
        audit_id: str | None = None,
        entity_type: str = "WORKFLOW",
        entity_id: str | None = None,
    ) -> dict[str, Any]:
        return {
            "audit_id": audit_id or _id("AUD"),
            "event_type": event_type,
            "actor": actor,
            "created_at": _now(),
            "summary": summary,
            "correlation_id": correlation_id,
            "entity_type": entity_type,
            "entity_id": entity_id or correlation_id,
        }

    def _part(self, part_id: str) -> dict[str, Any]:
        part = self.repo.one("parts", "part_id", part_id)
        if not part:
            raise EvidenceError(f"No governed part record exists for {part_id}.")
        return part

    def _plant(self, plant_id: str) -> dict[str, Any]:
        plant = self.repo.one("plants", "plant_id", plant_id)
        if not plant:
            raise EvidenceError(f"No governed plant record exists for {plant_id}.")
        return plant

    def trace_order_impact(
        self,
        part_id: str,
        delay_days: int,
        supplier_id: str | None = None,
    ) -> dict[str, Any]:
        if delay_days < 1 or delay_days > 90:
            raise ValueError("delay_days must be between 1 and 90")
        part = self._part(part_id)
        active_disrupted_suppliers = {
            item["supplier_id"]
            for item in self.repo.all("disruption_events")
            if item["status"] == "ACTIVE"
        }
        inbound = [
            shipment
            for shipment in self.repo.all("shipments")
            if shipment["part_id"] == part_id
            and shipment["status"] == "IN_TRANSIT"
        ]
        candidate_suppliers = {
            shipment["supplier_id"]
            for shipment in inbound
            if shipment["supplier_id"] in active_disrupted_suppliers
        }
        if supplier_id:
            disrupted_suppliers = {supplier_id}
            if supplier_id not in candidate_suppliers:
                raise EvidenceError(
                    f"No active governed disruption and inbound supply exists for {supplier_id} / {part_id}."
                )
        else:
            if len(candidate_suppliers) > 1:
                raise ValueError(
                    f"supplier_id is required because multiple disrupted suppliers affect {part_id}."
                )
            disrupted_suppliers = candidate_suppliers
        if not inbound or not disrupted_suppliers:
            raise EvidenceError(f"No confirmed inbound supply exists for {part_id}.")

        customers = {item["customer_id"]: item for item in self.repo.all("customers")}
        orders = sorted(
            [
                order for order in self.repo.all("sales_orders")
                if order["part_id"] == part_id and order["status"] == "OPEN"
            ],
            key=lambda item: item["required_date"],
        )
        inventory_by_plant = {
            item["plant_id"]: item for item in self.repo.all("inventory") if item["part_id"] == part_id
        }
        missing_inventory_plants = sorted(
            {order["plant_id"] for order in orders if order["plant_id"] not in inventory_by_plant}
        )
        if missing_inventory_plants:
            raise EvidenceError(
                f"Inventory evidence missing for {part_id} at {', '.join(missing_inventory_plants)}."
            )
        allocatable_by_plant = {
            plant_id: max(item["on_hand"] - item["safety_stock"], 0)
            for plant_id, item in inventory_by_plant.items()
        }
        projected_inbound_by_plant: dict[str, list[dict[str, Any]]] = {}
        for shipment in inbound:
            projected_eta = _parse_date(shipment["promised_date"])
            if shipment["supplier_id"] in disrupted_suppliers:
                projected_eta += timedelta(days=delay_days)
            plant_id = shipment["plant_id"]
            projected_inbound_by_plant.setdefault(plant_id, []).append(
                {
                    **shipment,
                    "projected_eta": projected_eta,
                    "scenario_delayed": shipment["supplier_id"] in disrupted_suppliers,
                }
            )

        affected: list[dict[str, Any]] = []
        protected: list[dict[str, Any]] = []
        cumulative_demand_by_plant: dict[str, int] = {}
        for order in orders:
            plant_id = order["plant_id"]
            required_date = _parse_date(order["required_date"])
            cumulative_demand_by_plant[plant_id] = (
                cumulative_demand_by_plant.get(plant_id, 0) + order["quantity"]
            )
            inbound_by_required_date = sum(
                shipment["quantity"]
                for shipment in projected_inbound_by_plant.get(plant_id, [])
                if shipment["projected_eta"] <= required_date
            )
            available_supply = allocatable_by_plant.get(plant_id, 0) + inbound_by_required_date
            shortage_quantity = max(
                cumulative_demand_by_plant[plant_id] - available_supply,
                0,
            )

            if shortage_quantity == 0:
                protected.append(
                    {
                        **order,
                        "protection_reason": "Quantity-aware supply is sufficient by the required date.",
                        "available_supply_by_required_date": available_supply,
                        "cumulative_demand": cumulative_demand_by_plant[plant_id],
                    }
                )
                continue

            customer = customers.get(order["customer_id"])
            if not customer:
                raise EvidenceError(f"Customer evidence missing for order {order['order_id']}.")
            disrupted_arrivals = [
                shipment["projected_eta"]
                for shipment in projected_inbound_by_plant.get(plant_id, [])
                if shipment["scenario_delayed"]
            ]
            delayed_eta = min(disrupted_arrivals, default=None)
            days_late = (delayed_eta - required_date).days if delayed_eta else None
            severity = "CRITICAL" if customer["tier"] == "Strategic" or (days_late or 0) >= 7 else "HIGH"
            reason = (
                f"Delayed inbound lands {days_late} days after required date"
                if days_late is not None and days_late > 0
                else f"Available supply is {shortage_quantity} units below cumulative demand"
            )
            affected.append(
                {
                    **order,
                    "customer_name": customer["customer_name"],
                    "customer_tier": customer["tier"],
                    "part_name": part["part_name"],
                    "impact_severity": severity,
                    "reason": reason,
                    "projected_supply_date": delayed_eta.isoformat() if delayed_eta else None,
                    "available_supply_by_required_date": available_supply,
                    "cumulative_demand": cumulative_demand_by_plant[plant_id],
                    "shortage_quantity": shortage_quantity,
                    "source_system": "ERP + TMS + GOVERNED_METRICS",
                }
            )

        return {
            "part_id": part_id,
            "part_name": part["part_name"],
            "supplier_id": next(iter(disrupted_suppliers)),
            "delay_days": delay_days,
            "affected_sales_orders": affected,
            "protected_sales_orders": protected,
            "revenue_at_risk": sum(order["order_value"] for order in affected),
            "metric_definition": REVENUE_AT_RISK_DEFINITION,
            "source_system": self.repo.source_system,
            "generated_at": _now(),
        }

    def get_inventory_risk(self, part_id: str, plant_id: str | None = None) -> dict[str, Any]:
        part = self._part(part_id)
        inventory_rows = [item for item in self.repo.all("inventory") if item["part_id"] == part_id]
        if plant_id:
            self._plant(plant_id)
            inventory_rows = [item for item in inventory_rows if item["plant_id"] == plant_id]
        if not inventory_rows:
            raise EvidenceError(f"No inventory snapshot exists for {part_id}{f' at {plant_id}' if plant_id else ''}.")

        disruptions = {item["supplier_id"]: item for item in self.repo.all("disruption_events") if item["status"] == "ACTIVE"}
        shipments = self.repo.all("shipments")
        results: list[dict[str, Any]] = []
        for row in inventory_rows:
            available = max(row["on_hand"] - row["safety_stock"], 0)
            coverage_days = floor(available / row["daily_demand"]) if row["daily_demand"] else 0
            as_of_date = _parse_date(row["snapshot_at"])
            shortage_date = as_of_date + timedelta(days=coverage_days + 1)
            sources = [
                item for item in self.repo.all("supplier_parts")
                if item["part_id"] == part_id
                and item["plant_id"] == row["plant_id"]
                and item["approved"] is True
            ]
            sources.sort(
                key=lambda item: (
                    item["supplier_id"] not in disruptions,
                    item["lead_time_days"],
                    item["supplier_id"],
                )
            )
            primary_source = sources[0] if sources else None
            lead_time_days = primary_source["lead_time_days"] if primary_source else 0
            lead_time_window_end = as_of_date + timedelta(days=lead_time_days)
            inbound: list[dict[str, Any]] = []
            for shipment in shipments:
                if shipment["part_id"] != part_id or shipment["plant_id"] != row["plant_id"] or shipment["status"] != "IN_TRANSIT":
                    continue
                delay = disruptions.get(shipment["supplier_id"], {}).get("delay_days", 0)
                projected_date = _parse_date(shipment["promised_date"]) + timedelta(days=delay)
                inbound.append(
                    {
                        "shipment_id": shipment["shipment_id"],
                        "quantity": shipment["quantity"],
                        "original_eta": shipment["promised_date"],
                        "projected_eta": projected_date.isoformat(),
                        "confirmed": True,
                    }
                )
            earliest_inbound = min((_parse_date(item["projected_eta"]) for item in inbound), default=None)
            inbound_inside_window = sum(
                item["quantity"]
                for item in inbound
                if _parse_date(item["projected_eta"]) <= lead_time_window_end
            )
            lead_time_demand = row["daily_demand"] * lead_time_days
            is_stockout_risk = row["on_hand"] + inbound_inside_window < lead_time_demand
            if earliest_inbound is None or not primary_source:
                risk_level = "INSUFFICIENT_EVIDENCE"
            elif is_stockout_risk and earliest_inbound > shortage_date + timedelta(days=5):
                risk_level = "CRITICAL"
            elif is_stockout_risk:
                risk_level = "HIGH"
            else:
                risk_level = "LOW"
            results.append(
                {
                    "part_id": part_id,
                    "part_name": part["part_name"],
                    "plant_id": row["plant_id"],
                    "available_inventory": row["on_hand"],
                    "allocatable_inventory": available,
                    "safety_stock": row["safety_stock"],
                    "daily_demand": row["daily_demand"],
                    "lead_time_days": lead_time_days,
                    "lead_time_window_end": lead_time_window_end.isoformat(),
                    "projected_demand_in_lead_time_window": lead_time_demand,
                    "confirmed_inbound_inside_window": inbound_inside_window,
                    "projected_shortage_date": shortage_date.isoformat(),
                    "confirmed_inbound_supply": inbound,
                    "is_stockout_risk": is_stockout_risk,
                    "risk_level": risk_level,
                    "source_system": "WMS + TMS",
                    "source_timestamp": row["snapshot_at"],
                }
            )
        return {"inventory_risk": results, "generated_at": _now(), "source_system": self.repo.source_system}

    def list_approved_alternatives(
        self,
        part_id: str,
        plant_id: str,
        delay_days: int = 14,
        disrupted_supplier_id: str | None = None,
    ) -> dict[str, Any]:
        self._part(part_id)
        self._plant(plant_id)
        if disrupted_supplier_id is None:
            active_suppliers = {
                event["supplier_id"]
                for event in self.repo.all("disruption_events")
                if event["status"] == "ACTIVE"
            }
            candidates = {
                item["supplier_id"]
                for item in self.repo.all("supplier_parts")
                if item["part_id"] == part_id
                and item["plant_id"] == plant_id
                and item["supplier_id"] in active_suppliers
            }
            if len(candidates) > 1:
                raise ValueError(
                    "disrupted_supplier_id is required because multiple disruptions affect this part and plant."
                )
            disrupted_supplier_id = next(iter(candidates), None)
        alternatives = [
            item for item in self.repo.all("supplier_parts")
            if item["part_id"] == part_id
            and item["plant_id"] == plant_id
            and item["approved"] is True
            and item["supplier_id"] != disrupted_supplier_id
        ]
        if not alternatives:
            raise EvidenceError(f"No approved alternative is available for {part_id} at {plant_id}.")

        supplier_names = {item["supplier_id"]: item["supplier_name"] for item in self.repo.all("suppliers")}
        at_risk = self.trace_order_impact(
            part_id,
            delay_days,
            disrupted_supplier_id,
        )["affected_sales_orders"]
        at_risk = [order for order in at_risk if order["plant_id"] == plant_id]
        shortage_quantity = max(
            (order["shortage_quantity"] for order in at_risk),
            default=0,
        )
        inventory_snapshot = next(
            (
                item for item in self.repo.all("inventory")
                if item["part_id"] == part_id and item["plant_id"] == plant_id
            ),
            None,
        )
        if not inventory_snapshot:
            raise EvidenceError(f"Inventory timing evidence is missing for {part_id} / {plant_id}.")
        as_of_date = _parse_date(inventory_snapshot["snapshot_at"])
        ranked = sorted(alternatives, key=lambda item: (item["lead_time_days"], -item["available_capacity"]))
        results = []
        for alternative in ranked:
            capacity = alternative["available_capacity"]
            arrival_date = as_of_date + timedelta(days=alternative["lead_time_days"])
            if shortage_quantity == 0:
                results.append(
                    {
                        **alternative,
                        "supplier_name": supplier_names[alternative["supplier_id"]],
                        "recommendation_rank": len(results) + 1,
                        "coverage_percent": 0,
                        "estimated_protected_revenue": 0,
                        "projected_arrival_date": arrival_date.isoformat(),
                        "shortage_quantity": 0,
                        "protected_quantity": 0,
                        "tradeoff": "Qualified contingency; the selected scenario currently requires no mitigation.",
                        "approval_evidence": "SUPPLIER_PART_PLANT qualification record",
                        "source_system": "Supplier Master",
                    }
                )
                continue
            timely_orders = [
                order for order in at_risk
                if arrival_date <= _parse_date(order["required_date"])
            ]
            if not timely_orders:
                continue
            remaining_capacity = capacity
            protected_revenue = 0.0
            previous_shortage = 0
            timely_shortage = 0
            for order in sorted(timely_orders, key=lambda item: (item["required_date"], item["order_id"])):
                if remaining_capacity <= 0:
                    break
                incremental_shortage = max(order["shortage_quantity"] - previous_shortage, 0)
                previous_shortage = max(previous_shortage, order["shortage_quantity"])
                timely_shortage += incremental_shortage
                covered_quantity = min(remaining_capacity, incremental_shortage)
                if incremental_shortage:
                    protected_revenue += order["order_value"] * covered_quantity / incremental_shortage
                remaining_capacity -= covered_quantity
            protected_quantity = min(capacity, timely_shortage)
            coverage = min(round(protected_quantity / shortage_quantity * 100), 100)
            rank = len(results) + 1
            if rank == 1:
                tradeoff = "Fastest qualified response with the strongest available coverage."
            elif coverage == 100:
                tradeoff = "Full shortage coverage with a higher lead-time or cost trade-off."
            else:
                tradeoff = "Lower-cost partial coverage; combine with allocation prioritization."
            results.append(
                {
                    **alternative,
                    "supplier_name": supplier_names[alternative["supplier_id"]],
                    "recommendation_rank": rank,
                    "coverage_percent": coverage,
                    "estimated_protected_revenue": round(protected_revenue),
                    "projected_arrival_date": arrival_date.isoformat(),
                    "shortage_quantity": shortage_quantity,
                    "protected_quantity": protected_quantity,
                    "tradeoff": tradeoff,
                    "approval_evidence": "SUPPLIER_PART_PLANT qualification record",
                    "source_system": "Supplier Master",
                }
            )
        if not results:
            raise EvidenceError(
                f"Approved alternatives exist for {part_id} / {plant_id}, but none can arrive before an exposed order is due."
            )
        return {
            "part_id": part_id,
            "plant_id": plant_id,
            "disrupted_supplier_id": disrupted_supplier_id,
            "mitigation_required": shortage_quantity > 0,
            "approved_alternatives": results,
            "excluded_unapproved_count": len(
                [
                    item for item in self.repo.all("supplier_parts")
                    if item["part_id"] == part_id and item["plant_id"] == plant_id and not item["approved"]
                ]
            ),
            "generated_at": _now(),
            "source_system": self.repo.source_system,
        }

    def compare_delay_scenarios(
        self,
        supplier_id: str,
        delay_days: list[int] | tuple[int, ...] = (3, 7, 14, 21),
    ) -> dict[str, Any]:
        unique_delays = sorted(set(delay_days))
        if not unique_delays or len(unique_delays) > 8:
            raise ValueError("Provide between one and eight delay scenarios.")
        if any(days < 1 or days > 90 for days in unique_delays):
            raise ValueError("Every delay scenario must be between 1 and 90 days.")

        scenarios = []
        for days in unique_delays:
            analysis = self.analyze_supplier_delay(
                supplier_id,
                days,
                record_audit=False,
            )
            summary = analysis["risk_summary"]
            scenarios.append(
                {
                    "delay_days": days,
                    "severity": summary["severity"],
                    "revenue_at_risk": summary["revenue_at_risk"],
                    "orders_at_risk": summary["impacted_orders"],
                    "plants_at_risk": len(analysis["affected_plants"]),
                    "strategic_customers_at_risk": len(
                        [
                            customer
                            for customer in analysis["affected_customers"]
                            if customer["tier"] == "Strategic"
                        ]
                    ),
                    "source_references": analysis["source_references"],
                }
            )

        first_exposure = next(
            (item for item in scenarios if item["revenue_at_risk"] > 0),
            None,
        )
        return {
            "supplier_id": supplier_id,
            "scenarios": scenarios,
            "first_exposure_delay_days": (
                first_exposure["delay_days"] if first_exposure else None
            ),
            "metric_definition": REVENUE_AT_RISK_DEFINITION,
            "source_system": self.repo.source_system,
            "generated_at": _now(),
        }

    def ask_supply_chain(
        self,
        question: str,
        actor: str = "Governed conversation router",
    ) -> dict[str, Any]:
        """Route a natural-language question only to governed deterministic tools."""

        normalized = " ".join(question.strip().split())
        lower = normalized.lower()
        blocked_phrases = (
            "ignore previous",
            "ignore policy",
            "bypass approval",
            "execute purchase order",
            "delete audit",
            "override guardrail",
        )
        if any(phrase in lower for phrase in blocked_phrases):
            correlation_id = _id("WF")
            audit = self._audit(
                "CONVERSATION_REJECTED_BY_POLICY",
                actor,
                "Rejected a request that attempted to bypass a governed boundary.",
                correlation_id,
            )
            return {
                "status": "REJECTED_BY_POLICY",
                "intent": "policy_bypass",
                "answer": "I can analyze governed supply-chain data, but I cannot bypass approval, invent records, delete audit evidence, or execute an external action.",
                "correlation_id": correlation_id,
                "audit_id": audit["audit_id"],
                "tool_calls": [],
                "source_references": [],
                "generated_at": _now(),
            }

        supplier_match = re.search(r"\bSUP-\d{3}\b", normalized, flags=re.IGNORECASE)
        part_match = re.search(r"\bPRT-[A-Z0-9]+\b", normalized, flags=re.IGNORECASE)
        plant_match = re.search(r"\bPLT-[A-Z0-9]+\b", normalized, flags=re.IGNORECASE)
        days_match = re.search(r"\b(\d{1,2})\s*(?:day|days)\b", lower)
        supplier_id = supplier_match.group(0).upper() if supplier_match else None
        part_id = part_match.group(0).upper() if part_match else None
        plant_id = plant_match.group(0).upper() if plant_match else None
        delay_days = int(days_match.group(1)) if days_match else None

        correlation_id = _id("WF")
        result: dict[str, Any]
        if any(term in lower for term in ("alternative", "alternate", "replacement", "mitigation supplier")):
            if not part_id or not plant_id:
                return self._clarification(
                    correlation_id,
                    "approved_alternatives",
                    "Include both a part ID and plant ID, for example PRT-AX14 at PLT-PUN.",
                    ["part_id", "plant_id"],
                    actor,
                )
            alternatives = self.list_approved_alternatives(
                part_id,
                plant_id,
                delay_days=delay_days or 14,
                disrupted_supplier_id=supplier_id,
            )
            ranked = alternatives["approved_alternatives"]
            result = {
                "status": "ANSWERED",
                "intent": "approved_alternatives",
                "answer": (
                    f"{len(ranked)} approved alternatives are available for {part_id} at {plant_id}. "
                    f"{ranked[0]['supplier_id']} ranks first with a {ranked[0]['lead_time_days']}-day lead time "
                    f"and {ranked[0]['coverage_percent']}% shortage coverage."
                ),
                "facts": [
                    {
                        "label": item["supplier_id"],
                        "value": f"{item['lead_time_days']} days · {item['coverage_percent']}% coverage · {item['cost_band']}",
                    }
                    for item in ranked
                ],
                "tool_calls": ["list_approved_alternatives"],
                "source_references": [
                    f"QUAL-{item['supplier_id']}-{part_id}-{plant_id}" for item in ranked
                ],
                "evidence": [],
            }
        elif any(term in lower for term in ("inventory", "stockout", "stock out", "shortage")):
            if not part_id:
                return self._clarification(
                    correlation_id,
                    "inventory_risk",
                    "Include a governed part ID, for example PRT-AX14.",
                    ["part_id"],
                    actor,
                )
            inventory = self.get_inventory_risk(part_id, plant_id)["inventory_risk"]
            result = {
                "status": "ANSWERED",
                "intent": "inventory_risk",
                "answer": " ".join(
                    f"{item['plant_id']} is {item['risk_level']} with shortage projected on {item['projected_shortage_date']}."
                    for item in inventory
                ),
                "facts": [
                    {
                        "label": item["plant_id"],
                        "value": f"{item['risk_level']} · {item['allocatable_inventory']} allocatable · {item['safety_stock']} protected",
                    }
                    for item in inventory
                ],
                "tool_calls": ["get_inventory_risk"],
                "source_references": [f"INV-{item['part_id']}-{item['plant_id']}" for item in inventory],
                "evidence": [],
            }
        elif any(term in lower for term in ("on time", "on-time", "otd", "delivery rate")):
            metrics = self.governed_metrics()
            rate = metrics["on_time_delivery_rate"]
            result = {
                "status": "ANSWERED",
                "intent": "governed_metric",
                "answer": f"Governed on-time delivery rate is {round(rate * 100)}% ({metrics['on_time_delivery_numerator']} of {metrics['deliveries_due_denominator']} received shipments).",
                "facts": [{"label": "OTD v1.0", "value": f"{round(rate * 100)}%"}],
                "tool_calls": ["governed_metrics"],
                "source_references": ["METRIC-OTD-V1"],
                "evidence": [],
            }
        elif any(term in lower for term in ("revenue", "order", "impact", "delay", "customer")):
            missing = []
            if not supplier_id:
                missing.append("supplier_id")
            if delay_days is None:
                missing.append("delay_days")
            if missing:
                return self._clarification(
                    correlation_id,
                    "supplier_delay_impact",
                    "Include a supplier ID and explicit delay, for example SUP-042 delayed by 14 days.",
                    missing,
                    actor,
                )
            analysis = self.analyze_supplier_delay(supplier_id, delay_days)
            summary = analysis["risk_summary"]
            result = {
                "status": "ANSWERED",
                "intent": "supplier_delay_impact",
                "answer": (
                    f"A {delay_days}-day delay from {supplier_id} puts {summary['impacted_orders']} orders "
                    f"and ${summary['revenue_at_risk']:,} of governed revenue at risk across "
                    f"{len(analysis['affected_plants'])} plants."
                ),
                "facts": [
                    {"label": "Revenue at risk · v1.0", "value": f"${summary['revenue_at_risk']:,}"},
                    {"label": "Orders at risk", "value": str(summary["impacted_orders"])},
                    {"label": "Strategic customers", "value": str(len([item for item in analysis["affected_customers"] if item["tier"] == "Strategic"]))},
                ],
                "tool_calls": ["analyze_supplier_delay", "trace_order_impact"],
                "source_references": analysis["source_references"],
                "evidence": analysis["evidence"],
                "metric_definition": analysis["metric_definition"],
                "correlation_id": analysis["correlation_id"],
            }
            correlation_id = analysis["correlation_id"]
        else:
            return self._clarification(
                correlation_id,
                "unknown",
                "Ask about a supplier delay, revenue/order impact, inventory risk, OTD, or approved alternatives.",
                ["supported_intent"],
                actor,
            )

        audit = self._audit(
            "CONVERSATIONAL_ANSWER_GENERATED",
            actor,
            f"Answered natural-language intent {result['intent']} using {', '.join(result['tool_calls'])}.",
            correlation_id,
        )
        result.update(
            {
                "correlation_id": correlation_id,
                "audit_id": audit["audit_id"],
                "generated_at": _now(),
                "source_system": self.repo.source_system,
                "answer_policy": "DETERMINISTIC_TOOLS_ONLY",
            }
        )
        return result

    def _clarification(
        self,
        correlation_id: str,
        intent: str,
        answer: str,
        missing_fields: list[str],
        actor: str,
    ) -> dict[str, Any]:
        audit = self._audit(
            "CONVERSATION_NEEDS_CLARIFICATION",
            actor,
            f"Refused to infer required fields for intent {intent}: {', '.join(missing_fields)}.",
            correlation_id,
        )
        return {
            "status": "NEEDS_CLARIFICATION",
            "intent": intent,
            "answer": answer,
            "missing_fields": missing_fields,
            "correlation_id": correlation_id,
            "audit_id": audit["audit_id"],
            "tool_calls": [],
            "source_references": [],
            "generated_at": _now(),
            "answer_policy": "NO_INFERENCE_FOR_REQUIRED_IDENTIFIERS",
        }

    def analyze_supplier_delay(
        self,
        supplier_id: str,
        delay_days: int,
        *,
        record_audit: bool = True,
        actor: str = "Supply Chain Management MCP Server",
    ) -> dict[str, Any]:
        if delay_days < 1 or delay_days > 90:
            raise ValueError("delay_days must be between 1 and 90")
        supplier = self.repo.one("suppliers", "supplier_id", supplier_id)
        if not supplier:
            raise EvidenceError(f"No governed supplier record exists for {supplier_id}.")
        shipments = [
            item for item in self.repo.all("shipments")
            if item["supplier_id"] == supplier_id and item["status"] == "IN_TRANSIT"
        ]
        if not shipments:
            raise EvidenceError(f"No open inbound shipments support an impact analysis for {supplier_id}.")

        parts_by_id = {item["part_id"]: item for item in self.repo.all("parts")}
        plants_by_id = {item["plant_id"]: item for item in self.repo.all("plants")}
        affected_part_ids = sorted({item["part_id"] for item in shipments})
        affected_plant_ids = sorted({item["plant_id"] for item in shipments})
        impacted_orders = []
        protected_orders = []
        for part_id in affected_part_ids:
            impact = self.trace_order_impact(part_id, delay_days, supplier_id)
            impacted_orders.extend(impact["affected_sales_orders"])
            protected_orders.extend(impact["protected_sales_orders"])
        impacted_orders.sort(key=lambda item: (-item["order_value"], item["order_id"]))
        revenue_at_risk = sum(item["order_value"] for item in impacted_orders)
        protected_order_value = sum(item["order_value"] for item in protected_orders)

        customer_counts: dict[str, dict[str, Any]] = {}
        for order in impacted_orders:
            customer_counts.setdefault(
                order["customer_id"],
                {
                    "customer_id": order["customer_id"],
                    "customer_name": order["customer_name"],
                    "tier": order["customer_tier"],
                    "orders_at_risk": 0,
                },
            )["orders_at_risk"] += 1

        shipment_output = []
        for shipment in shipments:
            shipment_output.append(
                {
                    "shipment_id": shipment["shipment_id"],
                    "part_id": shipment["part_id"],
                    "plant_id": shipment["plant_id"],
                    "quantity": shipment["quantity"],
                    "original_eta": shipment["promised_date"],
                    "delayed_eta": (_parse_date(shipment["promised_date"]) + timedelta(days=delay_days)).isoformat(),
                    "status": "DELAYED",
                    "source_system": shipment["source_system"],
                    "observed_at": shipment.get("updated_at"),
                    "evidence_status": "SCENARIO_PROJECTION",
                }
            )

        documents = [item for item in self.repo.all("supplier_documents") if item["supplier_id"] == supplier_id]
        evidence = [
            {
                "reference_id": item["document_id"],
                "source_type": "Supplier notice",
                "title": item["title"],
                "detail": item["detail"],
                "source_system": item["source_system"],
                "observed_at": item["observed_at"],
                "evidence_status": "RECORDED",
            }
            for item in documents
        ]
        for shipment in shipment_output:
            evidence.append(
                {
                    "reference_id": shipment["shipment_id"],
                    "source_type": "Shipment scenario",
                    "title": f"{plants_by_id[shipment['plant_id']]['city']} projected inbound ETA",
                    "detail": f"Scenario projects {shipment['quantity']} units of {shipment['part_id']} from {shipment['original_eta']} to {shipment['delayed_eta']}.",
                    "source_system": shipment["source_system"],
                    "observed_at": shipment["observed_at"],
                    "evidence_status": shipment["evidence_status"],
                }
            )
        metric_source = (
            "Snowflake governed entity views + deterministic metric v1.0"
            if self.repo.mode == "snowflake"
            else "Governed fixture + deterministic metric v1.0"
        )
        evidence.append(
            {
                "reference_id": "METRIC-RAR-V1",
                "source_type": "Governed metric",
                "title": "Revenue at risk · v1.0",
                "detail": REVENUE_AT_RISK_DEFINITION,
                "source_system": metric_source,
                "observed_at": _now(),
                "evidence_status": "DERIVED",
            }
        )

        correlation_id = _id("WF")
        strategic_customers = len(
            [item for item in customer_counts.values() if item["tier"] == "Strategic"]
        )
        if impacted_orders:
            narrative = (
                f"{len(impacted_orders)} open orders fail the governed availability test at a "
                f"{delay_days}-day delay. {strategic_customers} strategic customer"
                f"{'s are' if strategic_customers != 1 else ' is'} exposed across "
                f"{len(affected_plant_ids)} plant{'s' if len(affected_plant_ids) != 1 else ''}."
            )
            severity = "CRITICAL" if revenue_at_risk >= 500_000 else "HIGH"
        else:
            narrative = (
                f"No open order fails the governed availability test at a {delay_days}-day delay. "
                "Safety stock remains protected and no customer revenue is currently exposed."
            )
            severity = "LOW"
        result = {
            "correlation_id": correlation_id,
            "generated_at": _now(),
            "source_system": self.repo.source_system,
            "supplier": supplier,
            "delay_days": delay_days,
            "risk_summary": {
                "severity": severity,
                "headline": f"{len(impacted_orders)} orders worth ${round(revenue_at_risk / 1000)}K require intervention",
                "narrative": narrative,
                "revenue_at_risk": revenue_at_risk,
                "impacted_orders": len(impacted_orders),
                "protected_order_value": protected_order_value,
            },
            "affected_parts": [parts_by_id[part_id] for part_id in affected_part_ids],
            "affected_plants": [plants_by_id[plant_id] for plant_id in affected_plant_ids],
            "affected_shipments": shipment_output,
            "open_orders": impacted_orders,
            "affected_customers": list(customer_counts.values()),
            "evidence": evidence,
            "source_references": [item["reference_id"] for item in evidence],
            "assumptions": [
                f"Confirmed inbound dates include the reported {delay_days}-day delay.",
                "Safety stock is protected before customer-order allocation.",
                "No unapproved suppliers are included in mitigation ranking.",
            ],
            "metric_definition": REVENUE_AT_RISK_DEFINITION,
        }
        if record_audit:
            audit = self._audit(
                "INVESTIGATION_COMPLETED",
                actor,
                f"Governed impact analysis completed for {supplier_id} / {delay_days} days.",
                correlation_id,
            )
            result["audit_id"] = audit["audit_id"]
        return result

    def governed_metrics(self) -> dict[str, Any]:
        received = [item for item in self.repo.all("shipments") if item["status"] == "RECEIVED"]
        on_time = [item for item in received if _parse_date(item["received_date"]) <= _parse_date(item["promised_date"])]
        inventory = []
        for part in self.repo.all("parts"):
            try:
                inventory.extend(self.get_inventory_risk(part["part_id"])["inventory_risk"])
            except EvidenceError:
                continue
        return {
            "on_time_delivery_rate": round(len(on_time) / len(received), 4) if received else None,
            "on_time_delivery_numerator": len(on_time),
            "deliveries_due_denominator": len(received),
            "plants_at_stockout_risk": len({item["plant_id"] for item in inventory if item["risk_level"] in {"HIGH", "CRITICAL"}}),
            "definitions": {
                "revenue_at_risk": REVENUE_AT_RISK_DEFINITION,
                "on_time_delivery_rate": "Deliveries received on or before the promised date divided by deliveries due.",
                "plant_stockout_risk": "Inventory plus confirmed inbound supply is below projected demand during the lead-time window.",
            },
            "source_system": self.repo.source_system,
        }

    def draft_mitigation(
        self,
        disruption_context: DisruptionContext,
        selected_option: MitigationOption,
        owner: str,
        owner_id: str | None = None,
    ) -> MitigationAction:
        qualification = next(
            (
                item for item in self.repo.all("supplier_parts")
                if item["supplier_id"] == selected_option.supplier_id
                and item["part_id"] == selected_option.part_id
                and item["plant_id"] == selected_option.plant_id
            ),
            None,
        )
        if not qualification or qualification["approved"] is not True:
            raise ValueError("Selected supplier-part-plant combination is not approved; no draft was created.")
        if selected_option.supplier_id == disruption_context.supplier_id:
            raise ValueError("The disrupted supplier cannot be selected as its own mitigation alternative.")

        correlation_id = disruption_context.correlation_id or _id("WF")
        disruption = next(
            (
                item
                for item in self.repo.all("disruption_events")
                if item["supplier_id"] == disruption_context.supplier_id
                and item["status"] == "ACTIVE"
            ),
            None,
        )
        if not disruption:
            raise EvidenceError(
                f"No active governed disruption exists for {disruption_context.supplier_id}."
            )
        self.repo.refresh_workflow_state()
        duplicate = next(
            (
                item for item in self.repo.mitigation_actions
                if item["disruption_id"] == disruption["disruption_id"]
                and item["part_id"] == selected_option.part_id
                and item["plant_id"] == selected_option.plant_id
                and item["status"] == "PENDING_APPROVAL"
            ),
            None,
        )
        if duplicate:
            raise GovernanceConflictError(
                f"Pending mitigation {duplicate['action_id']} already covers this disruption, part, and plant."
            )
        action_id = _id("ACT")
        audit_id = _id("AUD")
        rationale = selected_option.tradeoff or (
            f"Approved alternative with {qualification['lead_time_days']}-day lead time, "
            f"{qualification['available_capacity']} units capacity, and {qualification['cost_band']} cost band."
        )
        action = MitigationAction(
            audit_id=audit_id,
            action_id=action_id,
            disruption_id=disruption["disruption_id"],
            correlation_id=correlation_id,
            status="PENDING_APPROVAL",
            action_type="SOURCE_FROM_APPROVED_ALTERNATIVE",
            part_id=selected_option.part_id,
            plant_id=selected_option.plant_id,
            proposed_supplier_id=selected_option.supplier_id,
            owner=owner,
            owner_id=owner_id or owner.lower().replace(" ", "."),
            rationale=rationale,
            created_at=_now(),
            version=1,
            policy_decision_id=_id("POL"),
            qualification_checked_at=_now(),
        )
        event = self._audit_event(
            "MITIGATION_DRAFTED",
            owner,
            f"Drafted approved-alternative mitigation {action_id}; no external action executed.",
            correlation_id,
            audit_id=audit_id,
            entity_type="MITIGATION_ACTION",
            entity_id=action_id,
        )
        self.repo.create_action_with_audit(action.model_dump(), event)
        return action

    def list_mitigations(self, status: str | None = None) -> dict[str, Any]:
        self.repo.refresh_workflow_state()
        actions = deepcopy(self.repo.mitigation_actions)
        if status:
            actions = [item for item in actions if item["status"] == status]
        actions.sort(key=lambda item: item["created_at"], reverse=True)
        return {
            "mitigations": actions,
            "count": len(actions),
            "status_filter": status,
            "source_system": self.repo.source_system,
            "generated_at": _now(),
        }

    def approve_mitigation(
        self,
        action_id: str,
        approver: str,
        approver_id: str | None = None,
        expected_version: int | None = None,
        reason: str = "Approved after governed review.",
        idempotency_key: str | None = None,
    ) -> MitigationAction:
        actor_id = approver_id or approver.lower().replace(" ", ".")
        cache_key = (
            f"approve:{action_id}:{actor_id}:{idempotency_key}"
            if idempotency_key
            else None
        )
        self.repo.refresh_workflow_state()
        with self.repo.lock:
            if cache_key and cache_key in self.repo.idempotency_results:
                return MitigationAction.model_validate(deepcopy(self.repo.idempotency_results[cache_key]))
            action = next((item for item in self.repo.mitigation_actions if item["action_id"] == action_id), None)
            if not action:
                raise EvidenceError(f"Mitigation action {action_id} does not exist.")
            if action["status"] != "PENDING_APPROVAL":
                raise GovernanceConflictError(
                    f"Mitigation action {action_id} is already {action['status']}."
                )
            if expected_version is not None and action["version"] != expected_version:
                raise GovernanceConflictError(
                    f"Mitigation action {action_id} changed from version {expected_version} to {action['version']}; reload before deciding."
                )
            if action["owner_id"] == actor_id:
                raise GovernanceAuthorizationError(
                    "Separation-of-duties policy forbids the draft owner from approving it."
                )
            qualification = next(
                (
                    item for item in self.repo.all("supplier_parts")
                    if item["supplier_id"] == action["proposed_supplier_id"]
                    and item["part_id"] == action["part_id"]
                    and item["plant_id"] == action["plant_id"]
                ),
                None,
            )
            if (
                not qualification
                or qualification["approved"] is not True
                or qualification["available_capacity"] <= 0
            ):
                raise ValueError("Approval blocked because supplier qualification or capacity is no longer valid.")
            previous_version = action["version"]
            snapshot = deepcopy(action)
            snapshot["status"] = "APPROVED"
            snapshot["approved_by"] = approver
            snapshot["approved_by_id"] = actor_id
            snapshot["approved_at"] = _now()
            snapshot["approval_reason"] = reason
            snapshot["qualification_checked_at"] = _now()
            snapshot["policy_decision_id"] = _id("POL")
            snapshot["version"] += 1
            audit = self._audit_event(
                "HUMAN_APPROVAL_RECORDED",
                approver,
                f"Approved {action_id} after role, separation-of-duties, version, and qualification checks; execution remains separate.",
                snapshot["correlation_id"],
                entity_type="MITIGATION_ACTION",
                entity_id=action_id,
            )
            snapshot["audit_id"] = audit["audit_id"]
            try:
                self.repo.apply_decision_with_audit(
                    snapshot,
                    audit,
                    cache_key,
                    previous_version,
                )
            except ValueError as exc:
                if "changed in Snowflake" in str(exc):
                    raise GovernanceConflictError(str(exc)) from exc
                raise
        return MitigationAction.model_validate(snapshot)

    def return_mitigation_for_revision(
        self,
        action_id: str,
        reviewer: str,
        reason: str,
        reviewer_id: str | None = None,
        expected_version: int | None = None,
        idempotency_key: str | None = None,
    ) -> MitigationAction:
        actor_id = reviewer_id or reviewer.lower().replace(" ", ".")
        cache_key = (
            f"revise:{action_id}:{actor_id}:{idempotency_key}"
            if idempotency_key
            else None
        )
        self.repo.refresh_workflow_state()
        with self.repo.lock:
            if cache_key and cache_key in self.repo.idempotency_results:
                return MitigationAction.model_validate(deepcopy(self.repo.idempotency_results[cache_key]))
            action = next((item for item in self.repo.mitigation_actions if item["action_id"] == action_id), None)
            if not action:
                raise EvidenceError(f"Mitigation action {action_id} does not exist.")
            if action["status"] != "PENDING_APPROVAL":
                raise GovernanceConflictError(
                    f"Mitigation action {action_id} is already {action['status']}."
                )
            if expected_version is not None and action["version"] != expected_version:
                raise GovernanceConflictError(
                    f"Mitigation action {action_id} changed from version {expected_version} to {action['version']}; reload before deciding."
                )
            previous_version = action["version"]
            snapshot = deepcopy(action)
            snapshot["status"] = "RETURNED_FOR_REVISION"
            snapshot["returned_by"] = reviewer
            snapshot["returned_by_id"] = actor_id
            snapshot["returned_at"] = _now()
            snapshot["revision_reason"] = reason
            snapshot["policy_decision_id"] = _id("POL")
            snapshot["version"] += 1
            audit = self._audit_event(
                "MITIGATION_RETURNED_FOR_REVISION",
                reviewer,
                f"Returned {action_id} for revision; no external action executed. Reason: {reason}",
                snapshot["correlation_id"],
                entity_type="MITIGATION_ACTION",
                entity_id=action_id,
            )
            snapshot["audit_id"] = audit["audit_id"]
            try:
                self.repo.apply_decision_with_audit(
                    snapshot,
                    audit,
                    cache_key,
                    previous_version,
                )
            except ValueError as exc:
                if "changed in Snowflake" in str(exc):
                    raise GovernanceConflictError(str(exc)) from exc
                raise
        return MitigationAction.model_validate(snapshot)

    def demo_bundle(self, supplier_id: str, delay_days: int) -> dict[str, Any]:
        # Dashboard hydration is a read-only projection. It must not create an
        # investigation audit event merely because the UI refreshed.
        analysis = self.analyze_supplier_delay(supplier_id, delay_days, record_audit=False)
        alternatives: list[dict[str, Any]] = []
        seen_pairs = set()
        for shipment in analysis["affected_shipments"]:
            pair = (shipment["part_id"], shipment["plant_id"])
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)
            results = self.list_approved_alternatives(
                *pair,
                delay_days=delay_days,
                disrupted_supplier_id=supplier_id,
            )["approved_alternatives"]
            alternatives.extend(results)
        alternatives.sort(key=lambda item: (item["lead_time_days"], -item["coverage_percent"]))
        alternatives = alternatives[:3]
        for rank, item in enumerate(alternatives, start=1):
            item["recommendation_rank"] = rank
        pending = sum(1 for item in self.repo.mitigation_actions if item["status"] == "PENDING_APPROVAL")
        repository_status = self.repo.status()
        required_evidence_count = len(analysis["affected_shipments"]) + 2
        evidence_coverage = min(
            100,
            round(len(analysis["evidence"]) / max(required_evidence_count, 1) * 100),
        )
        return {
            "summary": {
                "active_disruptions": len([item for item in self.repo.all("disruption_events") if item["status"] == "ACTIVE"]),
                "revenue_at_risk": analysis["risk_summary"]["revenue_at_risk"],
                "plants_at_risk": self.governed_metrics()["plants_at_stockout_risk"],
                "orders_at_risk": analysis["risk_summary"]["impacted_orders"],
                "pending_approvals": pending,
            },
            "analysis": analysis,
            "alternatives": alternatives,
            "audit_events": deepcopy(self.repo.audit_events[:8]),
            "provenance": {
                "repository_mode": repository_status["mode"],
                "source_system": repository_status["source_system"],
                "snapshot_loaded_at": repository_status["snapshot_loaded_at"],
                "metric_lineage": (
                    "GOVERNED entity views → deterministic metric v1.0"
                    if repository_status["mode"] == "snowflake"
                    else "Governed fixture → deterministic metric v1.0"
                ),
                "metric_engine": "DETERMINISTIC_PYTHON_V1",
                "query_ids": repository_status["last_query_ids"],
                "semantic_validation": repository_status["semantic_validation"],
                "database_zones": repository_status["database_zones"],
                "evidence_coverage_percent": evidence_coverage,
                "policy_checks": [
                    "governed-identifiers",
                    "protected-safety-stock",
                    "approved-alternatives-only",
                    "draft-only-action",
                    "role-authorization",
                    "separation-of-duties",
                    "versioned-idempotent-decision",
                ],
            },
        }


service = SupplyChainService()
