from __future__ import annotations

import argparse
import json
from typing import Any

import snowflake.connector


CHECKS = {
    "account_credit_limit": (
        "SHOW PARAMETERS LIKE 'CORTEX_CODE_CLI_DAILY_EST_CREDIT_LIMIT_PER_USER' IN ACCOUNT"
    ),
    "user_grants": "SHOW GRANTS TO USER SHINGLOO",
    "available_models": "SHOW CORTEX BASE MODELS IN SCHEMA SNOWFLAKE.MODELS",
}


def main() -> None:
    parser = argparse.ArgumentParser(description="Run read-only CoCo access diagnostics.")
    parser.add_argument("--connection", default="supplychain-hackathon-admin")
    args = parser.parse_args()

    output: dict[str, Any] = {}
    connection = snowflake.connector.connect(connection_name=args.connection)
    try:
        cursor = connection.cursor(snowflake.connector.DictCursor)
        for name, sql in CHECKS.items():
            try:
                cursor.execute(sql)
                rows = cursor.fetchall()
                output[name] = {
                    "status": "PASS",
                    "query_id": cursor.sfqid,
                    "rows": rows[:30],
                    "row_count": len(rows),
                }
            except Exception as exc:
                output[name] = {
                    "status": "FAIL",
                    "query_id": getattr(cursor, "sfqid", None),
                    "error": f"{type(exc).__name__}: {exc}",
                }
        cursor.close()
    finally:
        connection.close()

    print(json.dumps(output, indent=2, default=str))


if __name__ == "__main__":
    main()
