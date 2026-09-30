from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import snowflake.connector


ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS = (
    ROOT / "snowflake/001_schema.sql",
    ROOT / "snowflake/002_seed.sql",
    ROOT / "snowflake/003_governed_semantic_views.sql",
    ROOT / "snowflake/004_validation.sql",
    ROOT / "snowflake/005_security_zones.sql",
    ROOT / "snowflake/006_core_isolation_fix.sql",
    ROOT / "snowflake/007_cortex_agent.sql",
)


def _contains_failed_assertion(rows: list[tuple[Any, ...]]) -> bool:
    """Treat a migration's explicit scalar FAIL result as a deployment failure."""
    return any(
        isinstance(value, str) and value.strip().upper() == "FAIL"
        for row in rows
        for value in row
    )


def deploy(connection_name: str) -> dict[str, Any]:
    evidence: dict[str, Any] = {
        "connection_name": connection_name,
        "status": "RUNNING",
        "migrations": [],
    }
    connection = snowflake.connector.connect(connection_name=connection_name)
    try:
        context_cursor = connection.cursor()
        context_cursor.execute(
            "SELECT CURRENT_ACCOUNT(), CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_REGION()"
        )
        account, role, warehouse, region = context_cursor.fetchone()
        evidence["context"] = {
            "account": account,
            "role": role,
            "warehouse": warehouse,
            "region": region,
            "query_id": context_cursor.sfqid,
        }
        context_cursor.close()

        for migration in MIGRATIONS:
            item: dict[str, Any] = {"file": str(migration.relative_to(ROOT)), "query_ids": []}
            try:
                for cursor in connection.execute_string(migration.read_text(encoding="utf-8")):
                    if cursor.sfqid:
                        item["query_ids"].append(cursor.sfqid)
                    if cursor.description:
                        rows = cursor.fetchall()
                        if rows:
                            item["result"] = rows
                            if _contains_failed_assertion(rows):
                                raise RuntimeError(
                                    f"Migration assertion returned FAIL in {migration.name}"
                                )
                    cursor.close()
                item["status"] = "PASS"
                evidence["migrations"].append(item)
            except Exception as exc:
                connection.rollback()
                item["status"] = "FAIL"
                item["error"] = f"{type(exc).__name__}: {exc}"
                evidence["migrations"].append(item)
                evidence["status"] = "FAIL"
                return evidence

        connection.commit()
        evidence["status"] = "PASS"
        return evidence
    finally:
        connection.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Deploy and validate SupplyChain Trust Graph in Snowflake."
    )
    parser.add_argument("--connection", default="supplychain-hackathon-admin")
    args = parser.parse_args()
    print(json.dumps(deploy(args.connection), indent=2, default=str))


if __name__ == "__main__":
    main()
