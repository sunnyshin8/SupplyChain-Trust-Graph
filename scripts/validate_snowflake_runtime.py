from __future__ import annotations

import argparse
import json
from typing import Any

import snowflake.connector


CHECKS = {
    "context": """
        SELECT CURRENT_ACCOUNT() AS ACCOUNT, CURRENT_ROLE() AS ROLE,
               CURRENT_WAREHOUSE() AS WAREHOUSE, CURRENT_DATABASE() AS DATABASE,
               CURRENT_SCHEMA() AS SCHEMA,
               CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES
    """,
    "golden_metric": """
        SELECT IFF(
          SUM(AT_RISK_VALUE) = 586000 AND COUNT_IF(IS_AT_RISK) = 3,
          'PASS', 'FAIL'
        ) AS STATUS,
        SUM(AT_RISK_VALUE) AS REVENUE_AT_RISK,
        COUNT_IF(IS_AT_RISK) AS ORDERS_AT_RISK
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.ORDER_RISK
        WHERE SUPPLIER_ID = 'SUP-042'
    """,
    "unapproved_supplier_gate": """
        SELECT IFF(COUNT(*) = 0, 'PASS', 'FAIL') AS STATUS,
               COUNT(*) AS LEAKED_ROWS
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLIER_PARTS
        WHERE SUPPLIER_ID = 'SUP-031'
          AND PART_ID = 'PRT-AX14'
          AND PLANT_ID = 'PLT-PUN'
          AND APPROVED = TRUE
    """,
    "semantic_view": """
        SELECT * FROM SEMANTIC_VIEW(
          SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLY_CHAIN_TRUST_GRAPH_SEMANTIC
          METRICS order_risk.revenue_at_risk, order_risk.orders_at_risk
          DIMENSIONS order_risk.supplier_id
          WHERE order_risk.supplier_id = 'SUP-042'
        )
    """,
    "workflow_zone": """
        SELECT COUNT(*) AS ACTION_COUNT
        FROM SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.MITIGATION_ACTIONS
    """,
    "audit_zone": """
        SELECT COUNT(*) AS AUDIT_COUNT
        FROM SUPPLYCHAIN_TRUST_GRAPH.AUDIT.AUDIT_EVENTS
    """,
}


def _explicit_assertion_failed(rows: list[dict[str, Any]]) -> bool:
    """Fail closed when a validation query returns an explicit non-PASS status."""
    statuses = [
        str(row["STATUS"]).upper()
        for row in rows
        if "STATUS" in row and row["STATUS"] is not None
    ]
    return bool(statuses) and any(status != "PASS" for status in statuses)


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate the least-privilege Snowflake runtime.")
    parser.add_argument("--connection", default="supplychain-hackathon")
    args = parser.parse_args()

    results: dict[str, Any] = {}
    connection = snowflake.connector.connect(connection_name=args.connection)
    try:
        cursor = connection.cursor(snowflake.connector.DictCursor)
        # A developer may also hold ACCOUNTADMIN. Disable secondary-role
        # inheritance so this validator proves the application role itself.
        cursor.execute("USE SECONDARY ROLES NONE")
        for name, sql in CHECKS.items():
            try:
                cursor.execute(sql)
                rows = cursor.fetchall()
                assertion_failed = _explicit_assertion_failed(rows)
                results[name] = {
                    "status": "FAIL" if assertion_failed else "PASS",
                    "query_id": cursor.sfqid,
                    "rows": rows,
                }
                if assertion_failed:
                    results[name]["error"] = (
                        "Validation query returned an explicit non-PASS status."
                    )
            except Exception as exc:
                results[name] = {
                    "status": "FAIL",
                    "query_id": getattr(cursor, "sfqid", None),
                    "error": f"{type(exc).__name__}: {exc}",
                }
        try:
            cursor.execute(
                "SELECT 1 FROM SUPPLYCHAIN_TRUST_GRAPH.CORE.SUPPLIERS LIMIT 1"
            )
            results["legacy_core_denied"] = {
                "status": "FAIL",
                "query_id": cursor.sfqid,
                "error": "Runtime role still has direct access to the legacy CORE zone.",
            }
        except Exception as exc:
            results["legacy_core_denied"] = {
                "status": "PASS",
                "query_id": getattr(cursor, "sfqid", None),
                "expected_denial": type(exc).__name__,
            }
        cursor.close()
    finally:
        connection.close()

    overall = all(item["status"] == "PASS" for item in results.values())
    print(json.dumps({"status": "PASS" if overall else "FAIL", "checks": results}, indent=2, default=str))
    raise SystemExit(0 if overall else 1)


if __name__ == "__main__":
    main()
