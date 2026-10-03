from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime
from decimal import Decimal
import json
import os
import time
from typing import Any
from zoneinfo import ZoneInfo

from .data import FixtureRepository


PUBLIC_READONLY_ROLE = "SUPPLYCHAIN_APP_READONLY"
SESSION_IDENTITY_QUERY = """
    SELECT CURRENT_ROLE() AS ACTIVE_ROLE,
           CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES
"""

ENTITY_QUERIES = {
    "suppliers": """
        SELECT SUPPLIER_ID, SUPPLIER_NAME, COUNTRY, RISK_TIER, STATUS,
               SOURCE_SYSTEM, UPDATED_AT
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLIERS
    """,
    "parts": """
        SELECT PART_ID, PART_NAME, CATEGORY, SOURCE_SYSTEM, UPDATED_AT
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.PARTS
    """,
    "plants": """
        SELECT PLANT_ID, PLANT_NAME, CITY, COUNTRY, SOURCE_SYSTEM, UPDATED_AT
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.PLANTS
    """,
    "supplier_parts": """
        SELECT SUPPLIER_ID, PART_ID, PLANT_ID, APPROVED, LEAD_TIME_DAYS,
               AVAILABLE_CAPACITY, COST_BAND, QUALIFIED_AT, SOURCE_SYSTEM
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLIER_PARTS
    """,
    "inventory": """
        SELECT PART_ID, PLANT_ID, ON_HAND, SAFETY_STOCK, DAILY_DEMAND,
               SNAPSHOT_AT, SOURCE_SYSTEM
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.INVENTORY
        QUALIFY ROW_NUMBER() OVER (
          PARTITION BY PART_ID, PLANT_ID ORDER BY SNAPSHOT_AT DESC
        ) = 1
    """,
    "customers": """
        SELECT CUSTOMER_ID, CUSTOMER_NAME, CUSTOMER_TIER AS TIER,
               SOURCE_SYSTEM, UPDATED_AT
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.CUSTOMERS
    """,
    "sales_orders": """
        SELECT ORDER_ID, CUSTOMER_ID, PART_ID, PLANT_ID, REQUIRED_DATE,
               ORDER_VALUE, QUANTITY, STATUS, SOURCE_SYSTEM, UPDATED_AT
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SALES_ORDERS
    """,
    "shipments": """
        SELECT SHIPMENT_ID, SUPPLIER_ID, PART_ID, PLANT_ID, ORDER_ID,
               QUANTITY, PROMISED_DATE, RECEIVED_DATE, STATUS,
               SOURCE_SYSTEM, UPDATED_AT
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SHIPMENTS
    """,
    "supplier_documents": """
        SELECT DOCUMENT_ID, SUPPLIER_ID, PART_ID, DOCUMENT_TYPE, TITLE,
               DETAIL, OBSERVED_AT, SOURCE_SYSTEM
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLIER_DOCUMENTS
    """,
    "disruption_events": """
        SELECT DISRUPTION_ID, SUPPLIER_ID, DELAY_DAYS, REPORTED_AT, STATUS,
               SOURCE_DOCUMENT_ID, CORRELATION_ID, SOURCE_SYSTEM
        FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.DISRUPTION_EVENTS
    """,
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _normalise_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key.lower(): _json_value(value) for key, value in row.items()}


def _timeout_seconds(name: str, default: int) -> int:
    try:
        return max(1, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _connection_timeouts() -> dict[str, int]:
    """Bound login and request waits so a stalled network cannot hang a session."""

    return {
        "login_timeout": _timeout_seconds("SNOWFLAKE_LOGIN_TIMEOUT_SECONDS", 20),
        "network_timeout": _timeout_seconds("SNOWFLAKE_NETWORK_TIMEOUT_SECONDS", 60),
    }


def _secondary_roles(value: Any) -> list[str] | None:
    """Parse CURRENT_SECONDARY_ROLES(); None means the format was not recognised."""

    if value in (None, ""):
        return []
    try:
        parsed = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return None
    if not isinstance(parsed, dict):
        return None
    return [role.strip() for role in str(parsed.get("roles") or "").split(",") if role.strip()]


def _metric_pair(row: dict[str, Any] | None) -> dict[str, int] | None:
    if not row:
        return None
    values = {key.lower().split(".")[-1]: value for key, value in row.items()}
    try:
        return {
            "revenue_at_risk": int(values["revenue_at_risk"]),
            "orders_at_risk": int(values["orders_at_risk"]),
        }
    except (KeyError, TypeError, ValueError):
        return None


class SnowflakeRepository(FixtureRepository):
    """Snowflake-backed governed repository using a named connection profile.

    The profile is shared with CoCo CLI through ~/.snowflake/connections.toml;
    no password, token, or account secret is read from this repository.
    """

    def __init__(
        self,
        connection_name: str | None,
        *,
        key_pair_settings: dict[str, str] | None = None,
    ) -> None:
        super().__init__()
        self.mode = "snowflake"
        self.source_system = "SNOWFLAKE_GOVERNED"
        self.connection_name = connection_name
        self._key_pair_settings = key_pair_settings
        self._snapshot_ttl_seconds = max(
            5,
            int(os.getenv("SUPPLYCHAIN_SNAPSHOT_TTL_SECONDS", "30")),
        )
        self._next_refresh_at = 0.0
        self.session_identity: dict[str, Any] = {}
        self._released = False
        self._connection = self._connect()
        try:
            self._load()
        except Exception:
            # Never leave a half-initialised session open behind a failed snapshot.
            self.close()
            raise

    def _connect(self):
        try:
            import snowflake.connector
        except ImportError as exc:  # pragma: no cover - depends on optional runtime
            raise RuntimeError(
                "Snowflake mode requires snowflake-connector-python. Run make install."
            ) from exc
        key_pair_settings = getattr(self, "_key_pair_settings", None) or {}
        private_key_pem = (
            key_pair_settings.get("private_key")
            or os.getenv("SNOWFLAKE_PRIVATE_KEY_PEM", "")
        ).replace("\\n", "\n").strip()
        token_path = os.getenv("SNOWFLAKE_TOKEN_PATH", "/snowflake/session/token")
        timeouts = _connection_timeouts()
        self.readonly_identity_required = False
        if os.path.isfile(token_path):
            with open(token_path, encoding="utf-8") as token_file:
                token = token_file.read().strip()
            host = os.getenv("SNOWFLAKE_HOST", "").strip()
            account = os.getenv("SNOWFLAKE_ACCOUNT", "").strip()
            if not host or not account or not token:
                raise RuntimeError(
                    "SPCS Snowflake mode requires SNOWFLAKE_HOST, SNOWFLAKE_ACCOUNT, and a mounted session token."
                )
            connection = snowflake.connector.connect(
                host=host,
                account=account,
                authenticator="oauth",
                token=token,
                warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
                database="SUPPLYCHAIN_TRUST_GRAPH",
                **timeouts,
            )
            self.connection_name = "SPCS_SERVICE_IDENTITY"
        elif private_key_pem:
            try:
                from cryptography.hazmat.primitives import serialization
            except ImportError as exc:  # pragma: no cover - connector dependency
                raise RuntimeError(
                    "Key-pair authentication requires the cryptography package."
                ) from exc

            account = (
                key_pair_settings.get("account")
                or os.getenv("SNOWFLAKE_ACCOUNT", "")
            ).strip()
            user = (
                key_pair_settings.get("user") or os.getenv("SNOWFLAKE_USER", "")
            ).strip()
            if not account or not user or not private_key_pem:
                raise RuntimeError(
                    "Key-pair mode requires SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, "
                    "and SNOWFLAKE_PRIVATE_KEY_PEM."
                )
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode("utf-8"),
                password=None,
            ).private_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PrivateFormat.PKCS8,
                encryption_algorithm=serialization.NoEncryption(),
            )
            role = (
                key_pair_settings.get("role")
                or os.getenv("SNOWFLAKE_ROLE", "SUPPLYCHAIN_APP_READONLY")
            ).strip()
            if role.upper() != "SUPPLYCHAIN_APP_READONLY":
                raise RuntimeError(
                    "External public runtimes are restricted to "
                    "SUPPLYCHAIN_APP_READONLY."
                )
            connection = snowflake.connector.connect(
                account=account,
                user=user,
                private_key=private_key,
                role=role,
                warehouse=(
                    key_pair_settings.get("warehouse")
                    or os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
                ),
                database="SUPPLYCHAIN_TRUST_GRAPH",
                **timeouts,
            )
            self.connection_name = "STREAMLIT_READONLY_SERVICE_IDENTITY"
            self.readonly_identity_required = True
        else:
            if not self.connection_name:
                raise RuntimeError("SNOWFLAKE_CONNECTION_NAME is required outside SPCS.")
            connection = snowflake.connector.connect(
                connection_name=self.connection_name,
                **timeouts,
            )
        try:
            connection.autocommit(False)
            # Do not let a developer's secondary roles (for example ACCOUNTADMIN)
            # silently widen the application's least-privilege runtime boundary.
            with connection.cursor() as cursor:
                cursor.execute("USE SECONDARY ROLES NONE")
        except Exception:
            try:
                connection.close()
            except Exception:
                pass
            raise
        return connection

    def _reconnect(self) -> None:
        if getattr(self, "_released", False):
            # A released runtime must not silently open a replacement session.
            raise RuntimeError("This Snowflake repository has been released.")
        connection = getattr(self, "_connection", None)
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass
        # _connect re-reads the mounted SPCS token on every attempt.
        self._connection = self._connect()

    def _ensure_connection(self) -> None:
        if self._connection.is_closed():
            self._reconnect()

    def _remember(self, cursor: Any) -> None:
        query_id = getattr(cursor, "sfqid", None)
        if query_id:
            self.last_query_ids.append(query_id)
            self.last_query_ids[:] = self.last_query_ids[-32:]

    def _fetch(self, sql: str, params: tuple[Any, ...] | None = None) -> list[dict[str, Any]]:
        from snowflake.connector import DictCursor

        with self.lock:
            # Reads are idempotent, so retry once on a fresh session when an
            # expired or dropped connection fails without reporting is_closed().
            for attempt in range(2):
                try:
                    self._ensure_connection()
                    with self._connection.cursor(DictCursor) as cursor:
                        cursor.execute(sql, params)
                        self._remember(cursor)
                        return [_normalise_row(row) for row in cursor.fetchall()]
                except Exception:
                    if attempt == 1:
                        raise
                    self._reconnect()
        raise RuntimeError("Snowflake read failed")

    def _verify_session_identity(self) -> dict[str, Any]:
        rows = self._fetch(SESSION_IDENTITY_QUERY)
        row = rows[0] if rows else {}
        active_role = str(row.get("active_role") or "").strip().upper()
        if (
            getattr(self, "readonly_identity_required", False)
            and active_role != PUBLIC_READONLY_ROLE
        ):
            raise RuntimeError(
                "The public key-pair session is not running as SUPPLYCHAIN_APP_READONLY."
            )
        secondary_roles = _secondary_roles(row.get("secondary_roles"))
        if secondary_roles:
            raise RuntimeError("Secondary roles must remain disabled for governed reads.")
        return {
            "active_role": active_role or "UNKNOWN",
            "secondary_roles": "NONE" if secondary_roles == [] else "UNVERIFIED",
            "connection_identity": self.connection_name,
        }

    def _load(self) -> None:
        # Fail closed before reading any governed data under an unexpected role.
        session_identity = self._verify_session_identity()
        loaded: dict[str, list[dict[str, Any]]] = {}
        for entity, query in ENTITY_QUERIES.items():
            loaded[entity] = self._fetch(query)

        actions = self._fetch(
            """
            SELECT AUDIT_ID, ACTION_ID, DISRUPTION_ID, PART_ID, PLANT_ID,
                   PROPOSED_SUPPLIER_ID, ACTION_TYPE, OWNER, OWNER_ID, STATUS,
                   RATIONALE, CREATED_AT, ACTION_VERSION AS VERSION,
                   POLICY_DECISION_ID, QUALIFICATION_CHECKED_AT, APPROVED_BY,
                   APPROVED_BY_ID, APPROVED_AT, APPROVAL_REASON, RETURNED_BY,
                   RETURNED_BY_ID, RETURNED_AT, REVISION_REASON, CORRELATION_ID
            FROM SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.MITIGATION_ACTIONS
            ORDER BY CREATED_AT
            """
        )
        audits = self._fetch(
            """
            SELECT AUDIT_ID, EVENT_TYPE, ACTOR, SUMMARY, ENTITY_TYPE, ENTITY_ID,
                   CORRELATION_ID, CREATED_AT, SOURCE_SYSTEM
            FROM SUPPLYCHAIN_TRUST_GRAPH.AUDIT.AUDIT_EVENTS
            ORDER BY CREATED_AT DESC
            """
        )
        idempotency = []
        if not getattr(self, "readonly_identity_required", False):
            idempotency = self._fetch(
                """
                SELECT CACHE_KEY, RESULT
                FROM SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.DECISION_IDEMPOTENCY
                """
            )
        governed_metric_rows = self._fetch(
            """
            SELECT COALESCE(SUM(AT_RISK_VALUE), 0) AS REVENUE_AT_RISK,
                   COUNT_IF(IS_AT_RISK) AS ORDERS_AT_RISK
            FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.ORDER_RISK
            WHERE SUPPLIER_ID = 'SUP-042'
            """
        )
        governed_metric_query_id = self.last_query_ids[-1] if self.last_query_ids else None
        semantic_rows = self._fetch(
            """
            SELECT * FROM SEMANTIC_VIEW(
              SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLY_CHAIN_TRUST_GRAPH_SEMANTIC
              METRICS order_risk.revenue_at_risk, order_risk.orders_at_risk
              DIMENSIONS order_risk.supplier_id
              WHERE order_risk.supplier_id = 'SUP-042'
            )
            """
        )
        semantic_query_id = self.last_query_ids[-1] if self.last_query_ids else None
        governed_metrics = _metric_pair(governed_metric_rows[0] if governed_metric_rows else None)
        semantic_metrics = _metric_pair(semantic_rows[0] if semantic_rows else None)
        semantic_status = (
            "MATCHED"
            if governed_metrics is not None and semantic_metrics == governed_metrics
            else "MISMATCH"
        )

        with self.lock:
            self.session_identity = session_identity
            self._data = loaded
            self.mitigation_actions = actions
            self.audit_events = audits
            self.idempotency_results = {
                item["cache_key"]: (
                    json.loads(item["result"])
                    if isinstance(item["result"], str)
                    else item["result"]
                )
                for item in idempotency
            }
            self.snapshot_loaded_at = datetime.now(ZoneInfo("Asia/Kolkata")).isoformat(
                timespec="seconds"
            )
            self._next_refresh_at = time.monotonic() + self._snapshot_ttl_seconds
            self.semantic_validation = {
                "status": semantic_status,
                "query_id": semantic_query_id,
                "governed_metric_query_id": governed_metric_query_id,
                "governed_metrics": governed_metrics,
                "semantic_metrics": semantic_metrics,
                "rows": semantic_rows,
            }
        self._connection.commit()

    def _refresh_if_stale(self) -> None:
        if time.monotonic() < self._next_refresh_at:
            return
        with self.lock:
            if time.monotonic() >= self._next_refresh_at:
                self._load()

    def refresh_workflow_state(self) -> None:
        # Decisions and approval queues must never rely on the snapshot TTL.
        self._load()

    def all(self, entity: str) -> list[dict[str, Any]]:
        self._refresh_if_stale()
        return super().all(entity)

    def status(self) -> dict[str, Any]:
        status = super().status()
        status["database_zones"] = {
            "source": "SUPPLYCHAIN_TRUST_GRAPH.SOURCE",
            "analytics": "SUPPLYCHAIN_TRUST_GRAPH.GOVERNED",
            "workflow": "SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW",
            "audit": "SUPPLYCHAIN_TRUST_GRAPH.AUDIT",
        }
        status["snapshot_ttl_seconds"] = self._snapshot_ttl_seconds
        status["semantic_validation"] = self.semantic_validation
        status["session_identity"] = dict(self.session_identity)
        return status

    def health_check(self) -> dict[str, Any]:
        """Prove the live session is usable, reconnecting once with a fresh SPCS token."""

        with self.lock:
            for attempt in range(2):
                try:
                    self._ensure_connection()
                    with self._connection.cursor() as cursor:
                        cursor.execute("SELECT 1")
                        cursor.fetchone()
                        self._remember(cursor)
                        query_id = cursor.sfqid
                    self._connection.commit()
                    return {"database": "snowflake", "connected": True, "query_id": query_id}
                except Exception:
                    try:
                        self._connection.rollback()
                    except Exception:
                        pass
                    if attempt == 1:
                        raise
                    self._reconnect()
        raise RuntimeError("Snowflake health check failed")

    def _insert_audit(self, cursor: Any, event: dict[str, Any]) -> None:
        cursor.execute(
            """
            INSERT INTO SUPPLYCHAIN_TRUST_GRAPH.AUDIT.AUDIT_EVENTS
              (AUDIT_ID, EVENT_TYPE, ACTOR, SUMMARY, ENTITY_TYPE, ENTITY_ID,
               CORRELATION_ID, CREATED_AT, SOURCE_SYSTEM)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'SUPPLYCHAIN_MCP')
            """,
            (
                event["audit_id"],
                event["event_type"],
                event["actor"],
                event["summary"],
                event.get("entity_type", "WORKFLOW"),
                event.get("entity_id", event["correlation_id"]),
                event["correlation_id"],
                event["created_at"],
            ),
        )
        self._remember(cursor)

    def append_audit(self, event: dict[str, Any]) -> None:
        with self.lock:
            try:
                with self._connection.cursor() as cursor:
                    self._insert_audit(cursor, event)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            self.audit_events.insert(0, deepcopy(event))

    def _insert_action(self, cursor: Any, action: dict[str, Any]) -> None:
        cursor.execute(
            """
            INSERT INTO SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.MITIGATION_ACTIONS
              (AUDIT_ID, ACTION_ID, DISRUPTION_ID, PART_ID, PLANT_ID,
               PROPOSED_SUPPLIER_ID, ACTION_TYPE, OWNER, OWNER_ID, STATUS,
               RATIONALE, CREATED_AT, ACTION_VERSION, POLICY_DECISION_ID,
               QUALIFICATION_CHECKED_AT, APPROVED_BY, APPROVED_BY_ID,
               APPROVED_AT, APPROVAL_REASON, RETURNED_BY, RETURNED_BY_ID,
               RETURNED_AT, REVISION_REASON, CORRELATION_ID)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                action["audit_id"], action["action_id"], action["disruption_id"],
                action["part_id"], action["plant_id"], action["proposed_supplier_id"],
                action["action_type"], action["owner"], action["owner_id"],
                action["status"], action["rationale"], action["created_at"],
                action["version"], action["policy_decision_id"],
                action["qualification_checked_at"], action.get("approved_by"),
                action.get("approved_by_id"), action.get("approved_at"),
                action.get("approval_reason"), action.get("returned_by"),
                action.get("returned_by_id"), action.get("returned_at"),
                action.get("revision_reason"), action["correlation_id"],
            ),
        )
        self._remember(cursor)

    def create_action_with_audit(
        self,
        action: dict[str, Any],
        event: dict[str, Any],
    ) -> None:
        with self.lock:
            try:
                with self._connection.cursor() as cursor:
                    self._insert_action(cursor, action)
                    self._insert_audit(cursor, event)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            self.mitigation_actions.append(deepcopy(action))
            self.audit_events.insert(0, deepcopy(event))

    def apply_decision_with_audit(
        self,
        action: dict[str, Any],
        event: dict[str, Any],
        cache_key: str | None,
        previous_version: int,
    ) -> None:
        with self.lock:
            try:
                with self._connection.cursor() as cursor:
                    if action["status"] == "APPROVED":
                        cursor.execute(
                            """
                            SELECT APPROVED, AVAILABLE_CAPACITY
                            FROM SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLIER_PARTS
                            WHERE SUPPLIER_ID = %s AND PART_ID = %s AND PLANT_ID = %s
                            """,
                            (
                                action["proposed_supplier_id"],
                                action["part_id"],
                                action["plant_id"],
                            ),
                        )
                        self._remember(cursor)
                        qualification = cursor.fetchone()
                        if (
                            not qualification
                            or qualification[0] is not True
                            or qualification[1] <= 0
                        ):
                            raise ValueError(
                                "Approval blocked by the live Snowflake qualification or capacity check."
                            )
                    cursor.execute(
                        """
                        UPDATE SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.MITIGATION_ACTIONS
                        SET AUDIT_ID = %s, STATUS = %s, ACTION_VERSION = %s,
                            POLICY_DECISION_ID = %s, QUALIFICATION_CHECKED_AT = %s,
                            APPROVED_BY = %s, APPROVED_BY_ID = %s, APPROVED_AT = %s,
                            APPROVAL_REASON = %s, RETURNED_BY = %s,
                            RETURNED_BY_ID = %s, RETURNED_AT = %s,
                            REVISION_REASON = %s
                        WHERE ACTION_ID = %s
                          AND ACTION_VERSION = %s
                          AND STATUS = 'PENDING_APPROVAL'
                        """,
                        (
                            action["audit_id"], action["status"], action["version"],
                            action["policy_decision_id"], action["qualification_checked_at"],
                            action.get("approved_by"), action.get("approved_by_id"),
                            action.get("approved_at"), action.get("approval_reason"),
                            action.get("returned_by"), action.get("returned_by_id"),
                            action.get("returned_at"), action.get("revision_reason"),
                            action["action_id"], previous_version,
                        ),
                    )
                    self._remember(cursor)
                    if cursor.rowcount != 1:
                        raise ValueError(
                            "The mitigation changed in Snowflake; reload before deciding."
                        )
                    self._insert_audit(cursor, event)
                    if cache_key:
                        cursor.execute(
                            """
                            INSERT INTO SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.DECISION_IDEMPOTENCY
                              (CACHE_KEY, ACTION_ID, RESULT, CREATED_AT)
                            SELECT %s, %s, PARSE_JSON(%s), CURRENT_TIMESTAMP()
                            WHERE NOT EXISTS (
                              SELECT 1
                              FROM SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.DECISION_IDEMPOTENCY
                              WHERE CACHE_KEY = %s
                            )
                            """,
                            (
                                cache_key,
                                action["action_id"],
                                json.dumps(action),
                                cache_key,
                            ),
                        )
                        self._remember(cursor)
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise
            super().apply_decision_with_audit(action, event, cache_key, previous_version)

    def close(self) -> None:
        with self.lock:
            self._released = True
            connection = getattr(self, "_connection", None)
            if connection is None:
                return
            try:
                if not connection.is_closed():
                    connection.close()
            except Exception:
                pass
