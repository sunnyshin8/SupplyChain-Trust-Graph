from __future__ import annotations

import argparse
import json
from typing import Any

import snowflake.connector

from backend.app.data import FixtureRepository
from backend.app.service import SupplyChainService


SCENARIOS = (3, 7, 14)

SCENARIO_SQL = """
WITH SCENARIOS(DELAY_DAYS) AS (
  SELECT COLUMN1 FROM VALUES (3), (7), (14)
),
PROJECTED_INBOUND_RAW AS (
  SELECT
    X.DELAY_DAYS,
    S.SUPPLIER_ID,
    S.PART_ID,
    S.PLANT_ID,
    S.QUANTITY AS INBOUND_QUANTITY,
    DATEADD('day', X.DELAY_DAYS, S.PROMISED_DATE) AS PROJECTED_ETA
  FROM SCENARIOS X
  JOIN SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SHIPMENTS S
    ON S.SUPPLIER_ID = 'SUP-042' AND S.STATUS = 'IN_TRANSIT'
),
PROJECTED_INBOUND AS (
  SELECT
    DELAY_DAYS,
    SUPPLIER_ID,
    PART_ID,
    PLANT_ID,
    SUM(INBOUND_QUANTITY) AS INBOUND_QUANTITY,
    MIN(PROJECTED_ETA) AS PROJECTED_ETA
  FROM PROJECTED_INBOUND_RAW
  GROUP BY DELAY_DAYS, SUPPLIER_ID, PART_ID, PLANT_ID
),
LATEST_INVENTORY AS (
  SELECT *
  FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.INVENTORY
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY PART_ID, PLANT_ID ORDER BY SNAPSHOT_AT DESC
  ) = 1
),
ORDER_CONTEXT AS (
  SELECT
    I.DELAY_DAYS,
    O.ORDER_ID,
    O.PART_ID,
    O.PLANT_ID,
    I.SUPPLIER_ID,
    O.REQUIRED_DATE,
    I.PROJECTED_ETA,
    O.ORDER_VALUE,
    O.QUANTITY AS ORDER_QUANTITY,
    GREATEST(L.ON_HAND - L.SAFETY_STOCK, 0) AS ALLOCATABLE_INVENTORY
  FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SALES_ORDERS O
  JOIN PROJECTED_INBOUND I
    ON I.PART_ID = O.PART_ID AND I.PLANT_ID = O.PLANT_ID
  JOIN LATEST_INVENTORY L
    ON L.PART_ID = O.PART_ID AND L.PLANT_ID = O.PLANT_ID
  WHERE O.STATUS = 'OPEN'
),
ALLOCATED AS (
  SELECT
    *,
    SUM(ORDER_QUANTITY) OVER (
      PARTITION BY DELAY_DAYS, SUPPLIER_ID, PART_ID, PLANT_ID
      ORDER BY REQUIRED_DATE, ORDER_ID
      ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS CUMULATIVE_ORDER_DEMAND
  FROM ORDER_CONTEXT
)
SELECT
  DELAY_DAYS,
  SUM(IFF(
    PROJECTED_ETA > REQUIRED_DATE
      AND ALLOCATABLE_INVENTORY < CUMULATIVE_ORDER_DEMAND,
    ORDER_VALUE,
    0
  )) AS REVENUE_AT_RISK,
  COUNT_IF(
    PROJECTED_ETA > REQUIRED_DATE
      AND ALLOCATABLE_INVENTORY < CUMULATIVE_ORDER_DEMAND
  ) AS ORDERS_AT_RISK
FROM ALLOCATED
GROUP BY DELAY_DAYS
ORDER BY DELAY_DAYS
"""


def _python_results() -> dict[int, dict[str, int]]:
    service = SupplyChainService(FixtureRepository())
    results: dict[int, dict[str, int]] = {}
    for delay_days in SCENARIOS:
        analysis = service.analyze_supplier_delay(
            "SUP-042",
            delay_days,
            record_audit=False,
        )
        results[delay_days] = {
            "revenue_at_risk": int(analysis["risk_summary"]["revenue_at_risk"]),
            "orders_at_risk": int(analysis["risk_summary"]["impacted_orders"]),
        }
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare Python workflow metrics with live governed Snowflake SQL."
    )
    parser.add_argument("--connection", default="supplychain-hackathon")
    args = parser.parse_args()

    python_results = _python_results()
    connection = snowflake.connector.connect(connection_name=args.connection)
    try:
        cursor = connection.cursor(snowflake.connector.DictCursor)
        cursor.execute("USE SECONDARY ROLES NONE")
        cursor.execute(SCENARIO_SQL)
        query_id = cursor.sfqid
        snowflake_results: dict[int, dict[str, int]] = {
            int(row["DELAY_DAYS"]): {
                "revenue_at_risk": int(row["REVENUE_AT_RISK"]),
                "orders_at_risk": int(row["ORDERS_AT_RISK"]),
            }
            for row in cursor.fetchall()
        }
        cursor.close()
    finally:
        connection.close()

    cases: list[dict[str, Any]] = []
    for delay_days in SCENARIOS:
        expected = python_results[delay_days]
        observed = snowflake_results.get(delay_days)
        cases.append(
            {
                "delay_days": delay_days,
                "status": "PASS" if observed == expected else "FAIL",
                "python": expected,
                "snowflake": observed,
            }
        )
    passed = sum(case["status"] == "PASS" for case in cases)
    result = {
        "suite": "Python-to-Snowflake multi-delay metric parity",
        "status": "PASS" if passed == len(cases) else "FAIL",
        "passed": passed,
        "total": len(cases),
        "connection": args.connection,
        "secondary_roles": "NONE",
        "snowflake_query_id": query_id,
        "cases": cases,
    }
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
