from __future__ import annotations

import argparse
from decimal import Decimal
import json
import re
import subprocess
from typing import Any
from uuid import uuid4

import snowflake.connector


DEFAULT_VIEW = (
    "SUPPLYCHAIN_TRUST_GRAPH.GOVERNED."
    "SUPPLY_CHAIN_TRUST_GRAPH_SEMANTIC"
)
GOVERNED_ORDER_RISK = "SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.ORDER_RISK"
DEFAULT_QUESTION = (
    "What revenue is at risk and how many orders are at risk for supplier SUP-042?"
)
FORBIDDEN_SQL = re.compile(
    r"\b(insert|update|delete|create|alter|drop|grant|revoke|call|copy|put|get|"
    r"merge|truncate)\b",
    re.IGNORECASE,
)


def _parse_cli_json(output: str) -> dict[str, Any]:
    start = output.find("{")
    if start < 0:
        raise ValueError("CoCo Analyst did not return a JSON response.")
    return json.loads(output[start:])


def _extract_generated_sql(
    result: str,
    expected_view: str,
    allowed_relations: tuple[str, ...] = (),
) -> str:
    match = re.search(r"```sql\s*(.*?)```", result, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("CoCo Analyst response did not contain fenced SQL.")

    sql = match.group(1).strip()
    uncommented = "\n".join(
        line for line in sql.splitlines() if not line.lstrip().startswith("--")
    ).strip()
    if uncommented.endswith(";"):
        uncommented = uncommented[:-1].rstrip()
    if ";" in uncommented:
        raise ValueError("CoCo Analyst generated more than one SQL statement.")
    if FORBIDDEN_SQL.search(uncommented):
        raise ValueError("CoCo Analyst generated non-read-only SQL.")

    normalized = " ".join(uncommented.lower().split())
    expected = expected_view.lower()
    if not allowed_relations:
        if not normalized.startswith("select * from semantic_view("):
            raise ValueError("CoCo Analyst SQL is outside the semantic-view allowlist.")
        if expected not in normalized:
            raise ValueError("CoCo Analyst SQL references an unexpected semantic view.")
        return sql

    if not (normalized.startswith("select ") or normalized.startswith("with ")):
        raise ValueError("CoCo Analyst SQL is not a read-only query.")

    permitted = {expected, *(relation.lower() for relation in allowed_relations)}
    qualified_objects = {
        value.lower()
        for value in re.findall(
            r"\b([a-z_][\w$]*\.[a-z_][\w$]*\.[a-z_][\w$]*)\b",
            uncommented,
            flags=re.IGNORECASE,
        )
    }
    if not qualified_objects or not qualified_objects.issubset(permitted):
        raise ValueError("CoCo Analyst SQL references a relation outside the allowlist.")

    cte_names = {
        value.lower()
        for value in re.findall(
            r"(?:\bwith\b|,)\s*([a-z_][\w$]*)\s+as\s*\(",
            uncommented,
            flags=re.IGNORECASE,
        )
    }
    relation_tokens = re.findall(
        r"\b(?:from|join)\s+([^\s,;]+)",
        uncommented,
        flags=re.IGNORECASE,
    )
    for token in relation_tokens:
        candidate = token.lstrip("(").lower()
        if candidate.startswith("semantic_view("):
            if expected not in normalized:
                raise ValueError("CoCo Analyst SQL references an unexpected semantic view.")
            continue
        if candidate in cte_names or candidate in permitted:
            continue
        raise ValueError(f"CoCo Analyst SQL relation is not allowlisted: {token}")
    return sql


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    return value


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Use CoCo CLI Cortex Analyst, execute only allowlisted semantic SQL, "
            "assert the golden result, and record attributable audit evidence."
        )
    )
    parser.add_argument("--connection", default="supplychain-hackathon")
    parser.add_argument("--view", default=DEFAULT_VIEW)
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument(
        "--record-audit",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    args = parser.parse_args()

    completed = subprocess.run(
        [
            "cortex",
            "analyst",
            "query",
            "-c",
            args.connection,
            "--view",
            args.view,
            args.question,
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(
            completed.stdout.strip() or completed.stderr.strip() or "CoCo Analyst failed."
        )

    analyst = _parse_cli_json(completed.stdout)
    analyst_result = str(analyst.get("result", ""))
    generated_sql = _extract_generated_sql(analyst_result, args.view)
    request_match = re.search(r"request_id:\s*([0-9a-f-]+)", analyst_result, re.I)
    request_id = request_match.group(1) if request_match else None

    connection = snowflake.connector.connect(connection_name=args.connection)
    connection.autocommit(False)
    audit_id = None
    audit_query_id = None
    audit_proof_query_id = None
    try:
        cursor = connection.cursor(snowflake.connector.DictCursor)
        cursor.execute("USE SECONDARY ROLES NONE")
        cursor.execute(generated_sql)
        result_query_id = cursor.sfqid
        rows = [
            {key.lower(): _json_value(value) for key, value in row.items()}
            for row in cursor.fetchall()
        ]
        expected = {
            "revenue_at_risk": 586_000,
            "orders_at_risk": 3,
            "supplier_id": "SUP-042",
        }
        parity_passed = len(rows) == 1 and all(
            rows[0].get(key) == value for key, value in expected.items()
        )
        if not parity_passed:
            raise ValueError(f"Cortex Analyst parity failed: {rows!r}")

        if args.record_audit:
            suffix = uuid4().hex[:8].upper()
            audit_id = f"AUD-COCO-{suffix}"
            correlation_id = f"COCO-{suffix}"
            cursor.execute(
                """
                INSERT INTO SUPPLYCHAIN_TRUST_GRAPH.AUDIT.AUDIT_EVENTS
                  (AUDIT_ID, EVENT_TYPE, ACTOR, SUMMARY, ENTITY_TYPE, ENTITY_ID,
                   CORRELATION_ID, CREATED_AT, SOURCE_SYSTEM)
                VALUES (%s, 'CORTEX_ANALYST_ANSWER', 'Snowflake CoCo CLI', %s,
                        'CORTEX_ANALYST_REQUEST', %s, %s, CURRENT_TIMESTAMP(),
                        'COCO_CLI')
                """,
                (
                    audit_id,
                    (
                        "CoCo Analyst generated allowlisted semantic SQL; "
                        f"Snowflake query {result_query_id} returned $586,000 / 3 orders."
                    ),
                    request_id or "REQUEST_ID_UNAVAILABLE",
                    correlation_id,
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
            audit_rows = cursor.fetchone()["AUDIT_ROWS"]
            if audit_rows != 1:
                raise ValueError("CoCo CLI audit evidence was not persisted exactly once.")
        else:
            connection.commit()
        cursor.close()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    print(
        json.dumps(
            {
                "status": "PASS",
                "credit_backed_service": "CORTEX_ANALYST",
                "connection": args.connection,
                "semantic_view": args.view,
                "question": args.question,
                "coco_request_id": request_id,
                "generated_sql": generated_sql,
                "snowflake_query_id": result_query_id,
                "rows": rows,
                "parity": {"status": "PASS", "expected": expected},
                "audit": {
                    "recorded": bool(args.record_audit),
                    "audit_id": audit_id,
                    "insert_query_id": audit_query_id,
                    "proof_query_id": audit_proof_query_id,
                    "source_system": "COCO_CLI" if args.record_audit else None,
                },
            },
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
