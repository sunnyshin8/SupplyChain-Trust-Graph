from __future__ import annotations

import argparse
import json
from typing import Any

from backend.app.service import SupplyChainService
from backend.app.snowflake_repository import SnowflakeRepository


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run read-only release checks against the layered Snowflake runtime."
    )
    parser.add_argument("--connection", default="supplychain-hackathon")
    args = parser.parse_args()

    repository = SnowflakeRepository(args.connection)
    try:
        service = SupplyChainService(repository)
        analysis = service.analyze_supplier_delay("SUP-042", 14, record_audit=False)
        alternatives = service.list_approved_alternatives("PRT-AX14", "PLT-PUN")
        status = repository.status()

        checks: list[dict[str, Any]] = [
            {
                "id": "golden_metric",
                "passed": analysis["risk_summary"]["revenue_at_risk"] == 586_000
                and analysis["risk_summary"]["impacted_orders"] == 3,
            },
            {
                "id": "unapproved_supplier_excluded",
                "passed": "SUP-031"
                not in {
                    item["supplier_id"]
                    for item in alternatives["approved_alternatives"]
                },
            },
            {
                "id": "semantic_view_matches_runtime",
                "passed": status["semantic_validation"]["status"] == "MATCHED"
                and status["semantic_validation"].get("semantic_metrics")
                == {
                    "revenue_at_risk": analysis["risk_summary"]["revenue_at_risk"],
                    "orders_at_risk": analysis["risk_summary"]["impacted_orders"],
                }
                and bool(status["semantic_validation"].get("query_id")),
            },
            {
                "id": "layered_security_zones",
                "passed": status["database_zones"]
                == {
                    "source": "SUPPLYCHAIN_TRUST_GRAPH.SOURCE",
                    "analytics": "SUPPLYCHAIN_TRUST_GRAPH.GOVERNED",
                    "workflow": "SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW",
                    "audit": "SUPPLYCHAIN_TRUST_GRAPH.AUDIT",
                },
            },
        ]
        passed = sum(1 for check in checks if check["passed"])
        result = {
            "suite": "Layered Snowflake read-only scorecard",
            "release_gate": "PASS" if passed == len(checks) else "FAIL",
            "passed": passed,
            "total": len(checks),
            "checks": checks,
            "snapshot_loaded_at": status["snapshot_loaded_at"],
            "query_ids": status["last_query_ids"],
            "semantic_validation": status["semantic_validation"],
        }
        print(json.dumps(result, indent=2, default=str))
        raise SystemExit(0 if result["release_gate"] == "PASS" else 1)
    finally:
        repository.close()


if __name__ == "__main__":
    main()
