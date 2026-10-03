from pathlib import Path

import pytest

from backend.app.snowflake_repository import SnowflakeRepository
from backend.app.snowflake_repository import _metric_pair
from scripts.validate_snowflake_runtime import _explicit_assertion_failed


ROOT = Path(__file__).resolve().parents[2]


def test_semantic_view_uses_cumulative_order_allocation() -> None:
    sql = (ROOT / "snowflake" / "003_governed_semantic_views.sql").read_text()

    assert "CUMULATIVE_ORDER_DEMAND" in sql
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in sql
    assert "IFF(PROJECTED_ETA <= REQUIRED_DATE, INBOUND_QUANTITY, 0)" in sql
    assert "< CUMULATIVE_ORDER_DEMAND" in sql
    assert "JOIN ACTIVE_DELAY D ON D.SUPPLIER_ID = S.SUPPLIER_ID" in sql
    assert "SP.SUPPLIER_ID = 'SUP-042'" not in sql
    assert "VERIFIED_AT 1790658000" in sql
    assert "ONBOARDING_QUESTION TRUE" in sql


def test_snowflake_action_contract_supports_backend_states_and_policy_fields() -> None:
    sql = (ROOT / "snowflake" / "001_schema.sql").read_text()

    assert "RETURNED_FOR_REVISION" in sql
    assert "ACTION_VERSION" in sql
    assert "POLICY_DECISION_ID" in sql
    assert "OWNER_ID" in sql


def test_snowflake_is_split_into_least_privilege_security_zones() -> None:
    sql = (ROOT / "snowflake" / "005_security_zones.sql").read_text()
    isolation_fix = (ROOT / "snowflake" / "006_core_isolation_fix.sql").read_text()
    repository = (ROOT / "backend" / "app" / "snowflake_repository.py").read_text()

    for schema in ("SOURCE", "GOVERNED", "WORKFLOW", "AUDIT"):
        assert f"CREATE SCHEMA IF NOT EXISTS {schema}" in sql
    assert "REVOKE USAGE ON SCHEMA CORE FROM ROLE SUPPLYCHAIN_APP_RUNTIME" in sql
    assert "REVOKE SELECT ON ALL VIEWS IN SCHEMA CORE" in sql
    assert "GRANT SELECT, REFERENCES ON SEMANTIC VIEW" in sql
    assert "SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SUPPLIERS" in repository
    assert "SUPPLYCHAIN_TRUST_GRAPH.WORKFLOW.MITIGATION_ACTIONS" in repository
    assert "SUPPLYCHAIN_TRUST_GRAPH.AUDIT.AUDIT_EVENTS" in repository
    assert "connection.autocommit(False)" in repository
    assert 'cursor.execute("USE SECONDARY ROLES NONE")' in repository
    assert "REVOKE SELECT ON ALL VIEWS IN SCHEMA CORE" in isolation_fix


def test_runtime_validator_disables_secondary_role_inheritance() -> None:
    validator = (ROOT / "scripts" / "validate_snowflake_runtime.py").read_text()

    assert 'cursor.execute("USE SECONDARY ROLES NONE")' in validator
    assert "CURRENT_SECONDARY_ROLES() AS SECONDARY_ROLES" in validator


def test_runtime_validator_fails_closed_on_explicit_failed_assertion() -> None:
    assert _explicit_assertion_failed([{"STATUS": "FAIL"}]) is True
    assert _explicit_assertion_failed([{"STATUS": "PASS"}]) is False
    assert _explicit_assertion_failed([{"ACCOUNT": "KJ18976"}]) is False


def test_semantic_metric_pair_is_strict_and_normalises_qualified_keys() -> None:
    assert _metric_pair(
        {
            "ORDER_RISK.REVENUE_AT_RISK": 586_000,
            "ORDER_RISK.ORDERS_AT_RISK": 3,
        }
    ) == {"revenue_at_risk": 586_000, "orders_at_risk": 3}
    assert _metric_pair({"REVENUE_AT_RISK": 586_000}) is None


def test_deployer_rejects_explicit_failed_sql_assertions() -> None:
    deployer = (ROOT / "scripts" / "deploy_snowflake.py").read_text()

    assert "_contains_failed_assertion" in deployer
    assert "Migration assertion returned FAIL" in deployer


def test_cortex_agent_is_secure_read_only_and_semantic_view_bound() -> None:
    sql = (ROOT / "snowflake" / "007_cortex_agent.sql").read_text()
    deployer = (ROOT / "scripts" / "deploy_snowflake.py").read_text()

    assert "CREATE OR REPLACE SECURE AGENT SUPPLYCHAIN_TRUST_AGENT" in sql
    assert 'type: "cortex_analyst_text_to_sql"' in sql
    assert "SUPPLY_CHAIN_TRUST_GRAPH_SEMANTIC" in sql
    assert "tool_not_accessible: reject" in sql
    assert "INSUFFICIENT_EVIDENCE" in sql
    assert "Never claim that a purchase order" in sql
    assert "CORTEX_AGENT_USER" in sql
    assert "GRANT USAGE ON AGENT SUPPLYCHAIN_TRUST_AGENT" in sql
    assert "007_cortex_agent.sql" in deployer


def test_forward_migration_can_run_without_replaying_seed_data() -> None:
    sql = (ROOT / "snowflake" / "008_quantity_aware_scenarios.sql").read_text()
    deployer = (ROOT / "scripts" / "deploy_snowflake.py").read_text()

    assert "CREATE OR REPLACE VIEW CORE.GOVERNED_ORDER_RISK" in sql
    assert "INBOUND_BY_REQUIRED_DATE" in sql
    assert "ALLOCATABLE_INVENTORY + INBOUND_BY_REQUIRED_DATE" in sql
    assert "008_quantity_aware_scenarios.sql" in deployer
    assert '"--start-at"' in deployer


def test_multi_delay_parity_harness_is_least_privilege_and_cumulative() -> None:
    harness = (ROOT / "scripts" / "verify_delay_parity.py").read_text()

    assert "SCENARIOS = (3, 7, 14)" in harness
    assert 'cursor.execute("USE SECONDARY ROLES NONE")' in harness
    assert "SUPPLYCHAIN_TRUST_GRAPH.GOVERNED.SALES_ORDERS" in harness
    assert "SUPPLYCHAIN_TRUST_GRAPH.CORE" not in harness
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW" in harness
    assert "record_audit=False" in harness


def test_hosting_infrastructure_is_owned_separately_from_runtime_data_role() -> None:
    foundation = (ROOT / "snowflake" / "hosting" / "001_spcs_foundation.sql").read_text()
    deployer = (ROOT / "scripts" / "deploy_spcs.py").read_text()

    assert "CREATE ROLE IF NOT EXISTS SUPPLYCHAIN_APP_SERVICE_OWNER" in foundation
    assert "GRANT ROLE SUPPLYCHAIN_APP_RUNTIME TO ROLE SUPPLYCHAIN_APP_SERVICE_OWNER" in foundation
    assert "BIND SERVICE ENDPOINT ON ACCOUNT TO ROLE SUPPLYCHAIN_APP_SERVICE_OWNER" in foundation
    assert "REVOKE BIND SERVICE ENDPOINT ON ACCOUNT FROM ROLE SUPPLYCHAIN_APP_RUNTIME" in foundation
    assert 'cursor.execute("USE ROLE SUPPLYCHAIN_APP_SERVICE_OWNER")' in deployer
    assert "TO ROLE SUPPLYCHAIN_APP_RUNTIME" not in deployer
    assert "REVOKE CREATE SERVICE" in deployer
    assert "FROM ROLE SUPPLYCHAIN_APP_SERVICE_OWNER" in deployer


def test_hosted_frontend_is_a_portable_static_export_with_same_origin_api_proxy() -> None:
    dockerfile = (ROOT / "deploy" / "spcs" / "frontend.Dockerfile").read_text()
    nginx = (ROOT / "deploy" / "spcs" / "nginx.conf").read_text()
    config = (ROOT / "frontend" / "next.config.ts").read_text()

    assert "NEXT_OUTPUT=export" in dockerfile
    assert "FROM --platform=${NATIVE_BUILDPLATFORM}" in dockerfile
    assert "nginx-unprivileged" in dockerfile
    assert "proxy_pass http://127.0.0.1:8000" in nginx
    assert "Sf-Context-Current-User" in nginx
    assert "output: isStaticExport ? 'export' : 'standalone'" in config
    assert "isStaticExport ? {}" in config


def test_live_health_probe_reconnects_with_a_fresh_service_token() -> None:
    repository = (ROOT / "backend" / "app" / "snowflake_repository.py").read_text()
    api = (ROOT / "backend" / "app" / "main.py").read_text()

    assert "def health_check" in repository
    assert "self._reconnect()" in repository
    assert 'cursor.execute("SELECT 1")' in repository
    assert '"dependency": service.repo.health_check()' in api


def test_public_streamlit_showcase_is_read_only_and_key_pair_scoped() -> None:
    repository = (ROOT / "backend" / "app" / "snowflake_repository.py").read_text()
    showcase = (ROOT / "streamlit_app.py").read_text()

    assert 'os.getenv("SNOWFLAKE_PRIVATE_KEY_PEM"' in repository
    assert 'role.upper() != "SUPPLYCHAIN_APP_READONLY"' in repository
    assert 'cursor.execute("USE SECONDARY ROLES NONE")' in repository
    assert "record_audit=False" in showcase
    assert "Prepare read-only draft preview" in showcase
    assert "Approval requires an authenticated independent reviewer" in showcase
    assert "draft_mitigation(" not in showcase
    assert "approve_mitigation(" not in showcase


def test_external_key_pair_connection_is_locked_to_readonly_role(monkeypatch) -> None:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    import snowflake.connector

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    monkeypatch.setenv("SNOWFLAKE_ACCOUNT", "ORG-ACCOUNT")
    monkeypatch.setenv("SNOWFLAKE_USER", "SUPPLYCHAIN_STREAMLIT_SVC")
    monkeypatch.setenv("SNOWFLAKE_PRIVATE_KEY_PEM", pem)
    monkeypatch.setenv("SNOWFLAKE_ROLE", "SUPPLYCHAIN_APP_READONLY")
    captured: dict = {}

    class FakeCursor:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return None

        def execute(self, sql):
            assert sql == "USE SECONDARY ROLES NONE"

    class FakeConnection:
        def __init__(self):
            self.autocommit_value = None

        def autocommit(self, value):
            self.autocommit_value = value

        def cursor(self):
            return FakeCursor()

    expected_connection = FakeConnection()

    def fake_connect(**kwargs):
        captured.update(kwargs)
        return expected_connection

    monkeypatch.setattr(snowflake.connector, "connect", fake_connect)
    repository = SnowflakeRepository.__new__(SnowflakeRepository)
    repository.connection_name = None

    assert repository._connect() is expected_connection
    assert captured["user"] == "SUPPLYCHAIN_STREAMLIT_SVC"
    assert captured["role"] == "SUPPLYCHAIN_APP_READONLY"
    assert captured["database"] == "SUPPLYCHAIN_TRUST_GRAPH"
    assert isinstance(captured["private_key"], bytes)
    assert expected_connection.autocommit_value is False
    assert repository.connection_name == "STREAMLIT_READONLY_SERVICE_IDENTITY"

    monkeypatch.setenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")
    with pytest.raises(RuntimeError, match="restricted to SUPPLYCHAIN_APP_READONLY"):
        repository._connect()
