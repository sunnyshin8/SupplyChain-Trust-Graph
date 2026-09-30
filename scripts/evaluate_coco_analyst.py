from __future__ import annotations

import argparse
from collections.abc import Callable
import json
import re
import subprocess
from typing import Any
from uuid import uuid4

import snowflake.connector

from scripts.verify_coco_analyst import (
    DEFAULT_VIEW,
    GOVERNED_ORDER_RISK,
    _extract_generated_sql,
    _json_value,
    _parse_cli_json,
)


def _metric_case(rows: list[dict[str, Any]]) -> bool:
    return rows == [
        {
            "revenue_at_risk": 586_000,
            "orders_at_risk": 3,
            "supplier_id": "SUP-042",
        }
    ]


def _order_case(rows: list[dict[str, Any]]) -> bool:
    actual = {
        (row.get("order_id"), row.get("customer_name"), row.get("customer_tier"))
        for row in rows
    }
    return actual == {
        ("SO-7101", "Apex Mobility", "Strategic"),
        ("SO-7102", "Meridian Robotics", "Priority"),
        ("SO-7103", "Helios Industrial", "Strategic"),
    }


def _plant_case(rows: list[dict[str, Any]]) -> bool:
    actual = {
        row.get("plant_id"): (
            row.get("plant_name"),
            row.get("revenue_at_risk"),
            row.get("orders_at_risk"),
        )
        for row in rows
    }
    return actual == {
        "PLT-PUN": ("Pune Assembly", 390_000, 2),
        "PLT-BLR": ("Bengaluru Systems", 196_000, 1),
    }


CASES: tuple[tuple[str, str, Callable[[list[dict[str, Any]]], bool]], ...] = (
    (
        "golden_metrics",
        "What revenue is at risk and how many orders are at risk for supplier SUP-042?",
        _metric_case,
    ),
    (
        "affected_orders",
        (
            "Which customer orders are at risk for supplier SUP-042? "
            "Include order ID, customer name, and customer tier."
        ),
        _order_case,
    ),
    (
        "plant_breakdown",
        "Break down revenue at risk and orders at risk by plant for supplier SUP-042.",
        _plant_case,
    ),
)


def _normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key.lower(): _json_value(value) for key, value in row.items()}
        for row in rows
    ]


def _run_analyst(connection_name: str, view: str, question: str) -> tuple[str, str | None]:
    completed = subprocess.run(
        [
            "cortex",
            "analyst",
            "query",
            "-c",
            connection_name,
            "--view",
            view,
            question,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stdout.strip()
            or completed.stderr.strip()
            or "CoCo Analyst failed."
        )
    payload = _parse_cli_json(completed.stdout)
    result = str(payload.get("result", ""))
    try:
        sql = _extract_generated_sql(
            result,
            view,
            allowed_relations=(GOVERNED_ORDER_RISK,),
        )
    except ValueError as exc:
        raise ValueError(f"{exc} Cortex Analyst response: {result}") from exc
    request_match = re.search(r"request_id:\s*([0-9a-f-]+)", result, re.I)
    return sql, request_match.group(1) if request_match else None


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Run a three-question, credit-backed CoCo Cortex Analyst evaluation "
            "against the governed semantic view."
        )
    )
    parser.add_argument("--connection", default="supplychain-hackathon")
    parser.add_argument("--view", default=DEFAULT_VIEW)
    args = parser.parse_args()

    connection = snowflake.connector.connect(connection_name=args.connection)
    connection.autocommit(False)
    results: list[dict[str, Any]] = []
    audit_id = None
    audit_query_id = None
    audit_proof_query_id = None
    try:
        cursor = connection.cursor(snowflake.connector.DictCursor)
        cursor.execute("USE SECONDARY ROLES NONE")
        for case_id, question, validator in CASES:
            sql, request_id = _run_analyst(args.connection, args.view, question)
            cursor.execute(sql)
            query_id = cursor.sfqid
            rows = _normalize_rows(cursor.fetchall())
            passed = validator(rows)
            results.append(
                {
                    "id": case_id,
                    "status": "PASS" if passed else "FAIL",
                    "question": question,
                    "coco_request_id": request_id,
                    "snowflake_query_id": query_id,
                    "generated_sql": sql,
                    "rows": rows,
                }
            )
            if not passed:
                raise ValueError(f"CoCo evaluation case {case_id} failed: {rows!r}")

        suffix = uuid4().hex[:8].upper()
        audit_id = f"AUD-COCO-EVAL-{suffix}"
        cursor.execute(
            """
            INSERT INTO SUPPLYCHAIN_TRUST_GRAPH.AUDIT.AUDIT_EVENTS
              (AUDIT_ID, EVENT_TYPE, ACTOR, SUMMARY, ENTITY_TYPE, ENTITY_ID,
               CORRELATION_ID, CREATED_AT, SOURCE_SYSTEM)
            VALUES (%s, 'CORTEX_ANALYST_EVAL', 'Snowflake CoCo CLI', %s,
                    'CORTEX_ANALYST_EVALUATION', %s, %s, CURRENT_TIMESTAMP(),
                    'COCO_CLI')
            """,
            (
                audit_id,
                (
                    f"{len(results)}/{len(CASES)} credit-backed Cortex Analyst "
                    "cases passed against the governed semantic view."
                ),
                audit_id,
                f"COCO-EVAL-{suffix}",
            ),
        )
        audit_query_id = cursor.sfqid
        connection.commit()
        cursor.execute(
            """
            SELECT COUNT(*) AS AUDIT_ROWS
            FROM SUPPLYCHAIN_TRUST_GRAPH.AUDIT.AUDIT_EVENTS
            WHERE AUDIT_ID = %s AND SOURCE_SYSTEM = 'COCO_CLI'
            """,
            (audit_id,),
        )
        audit_proof_query_id = cursor.sfqid
        if cursor.fetchone()["AUDIT_ROWS"] != 1:
            raise ValueError("CoCo evaluation audit evidence was not persisted once.")
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "suite": "CoCo Cortex Analyst governed evaluation",
                "status": "PASS",
                "credit_backed_service": "CORTEX_ANALYST",
                "passed": len(results),
                "total": len(CASES),
                "semantic_view": args.view,
                "cases": results,
                "audit": {
                    "audit_id": audit_id,
                    "insert_query_id": audit_query_id,
                    "proof_query_id": audit_proof_query_id,
                    "source_system": "COCO_CLI",
                },
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
