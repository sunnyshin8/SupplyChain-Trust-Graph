from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import time
from typing import Any

import snowflake.connector


ROOT = Path(__file__).resolve().parents[1]
DATABASE = "SUPPLYCHAIN_TRUST_GRAPH"
SCHEMA = "APP"
REPOSITORY = "SUPPLYCHAIN_IMAGES"
POOL = "SUPPLYCHAIN_APP_POOL"
SERVICE = "SUPPLYCHAIN_TRUST_GRAPH_SERVICE"


def _run(command: list[str], *, stdin: str | None = None) -> str:
    result = subprocess.run(
        command,
        cwd=ROOT,
        input=stdin,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        safe_command = " ".join(command[:3])
        raise RuntimeError(
            f"Command failed ({safe_command}): {result.stderr.strip() or result.stdout.strip()}"
        )
    return result.stdout


def _registry_login(snow_binary: str, connection_name: str) -> Path:
    _run(
        [
            snow_binary,
            "spcs",
            "image-registry",
            "login",
            "--connection",
            connection_name,
            "--silent",
        ]
    )
    authfile = Path.home() / ".docker/config.json"
    if not authfile.is_file():
        raise RuntimeError("Snowflake CLI login did not create a Docker credential file.")
    return authfile


def _ensure_podman(podman_binary: str, machine_name: str) -> str:
    probe = subprocess.run(
        [podman_binary, "info", "--format", "{{.Host.Arch}}"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    if probe.returncode:
        _run([podman_binary, "machine", "start", machine_name])
    architecture = _run(
        [podman_binary, "info", "--format", "{{.Host.Arch}}"],
    ).strip()
    if architecture not in {"amd64", "arm64"}:
        raise RuntimeError(f"Unsupported Podman builder architecture: {architecture}")
    return architecture


def _execute_file(connection: Any, path: Path) -> list[str]:
    query_ids: list[str] = []
    for cursor in connection.execute_string(path.read_text(encoding="utf-8")):
        if cursor.sfqid:
            query_ids.append(cursor.sfqid)
        cursor.close()
    connection.commit()
    return query_ids


def _repository_url(connection: Any) -> str:
    cursor = connection.cursor(snowflake.connector.DictCursor)
    try:
        cursor.execute(
            f"SHOW IMAGE REPOSITORIES LIKE '{REPOSITORY}' IN SCHEMA {DATABASE}.{SCHEMA}"
        )
        rows = cursor.fetchall()
        if not rows:
            raise RuntimeError("Snowflake image repository was not created.")
        normalised = {key.lower(): value for key, value in rows[0].items()}
        return str(normalised["repository_url"])
    finally:
        cursor.close()


def _render_spec(tag: str, planner_users: str, approver_users: str) -> str:
    template = (ROOT / "deploy/spcs/service-spec.template.yaml").read_text(encoding="utf-8")
    return (
        template.replace("__IMAGE_TAG__", tag)
        .replace("__PLANNER_USERS__", planner_users)
        .replace("__APPROVER_USERS__", approver_users)
    )


def _service_exists(connection: Any) -> bool:
    cursor = connection.cursor()
    try:
        cursor.execute(f"SHOW SERVICES LIKE '{SERVICE}' IN SCHEMA {DATABASE}.{SCHEMA}")
        return cursor.fetchone() is not None
    finally:
        cursor.close()


def _deploy_service(connection: Any, spec: str) -> str:
    cursor = connection.cursor()
    try:
        cursor.execute("USE ROLE SUPPLYCHAIN_APP_SERVICE_OWNER")
        cursor.execute(f"USE DATABASE {DATABASE}")
        cursor.execute(f"USE SCHEMA {SCHEMA}")
        if _service_exists(connection):
            cursor.execute(f"ALTER SERVICE {SERVICE} FROM SPECIFICATION $$\n{spec}\n$$")
        else:
            cursor.execute(
                f"""CREATE SERVICE {SERVICE}
                IN COMPUTE POOL {POOL}
                FROM SPECIFICATION $$
{spec}
$$
                AUTO_SUSPEND_SECS = 0
                AUTO_RESUME = TRUE
                MIN_INSTANCES = 1
                MIN_READY_INSTANCES = 1
                MAX_INSTANCES = 1
                QUERY_WAREHOUSE = COMPUTE_WH
                COMMENT = 'Governed supply-chain decision service hosted entirely in Snowflake'"""
            )
        deploy_query_id = cursor.sfqid
        cursor.execute("USE ROLE ACCOUNTADMIN")
        cursor.execute(
            f"GRANT SERVICE ROLE {DATABASE}.{SCHEMA}.{SERVICE}!UI_USAGE "
            "TO ROLE SUPPLYCHAIN_APP_READONLY"
        )
        cursor.execute(
            f"REVOKE CREATE SERVICE ON SCHEMA {DATABASE}.{SCHEMA} "
            "FROM ROLE SUPPLYCHAIN_APP_SERVICE_OWNER"
        )
        cursor.execute(
            "REVOKE BIND SERVICE ENDPOINT ON ACCOUNT "
            "FROM ROLE SUPPLYCHAIN_APP_SERVICE_OWNER"
        )
        cursor.execute("USE ROLE SUPPLYCHAIN_APP_SERVICE_OWNER")
        return deploy_query_id
    finally:
        cursor.close()


def _service_evidence(connection: Any, wait_seconds: int) -> dict[str, Any]:
    deadline = time.monotonic() + wait_seconds
    status = "PENDING"
    containers: list[dict[str, Any]] = []
    while time.monotonic() < deadline:
        cursor = connection.cursor(snowflake.connector.DictCursor)
        try:
            cursor.execute(f"SHOW SERVICES LIKE '{SERVICE}' IN SCHEMA {DATABASE}.{SCHEMA}")
            row = cursor.fetchone()
            if row:
                service = {key.lower(): value for key, value in row.items()}
                status = str(service.get("status", status))
            cursor.execute(
                f"SHOW SERVICE CONTAINERS IN SERVICE {DATABASE}.{SCHEMA}.{SERVICE}"
            )
            containers = [
                {key.lower(): value for key, value in row.items()}
                for row in cursor.fetchall()
            ]
            containers_ready = containers and all(
                str(
                    item.get("container_status")
                    or item.get("ready_status")
                    or item.get("status", "")
                ).upper()
                in {"READY", "RUNNING"}
                for item in containers
            )
            if status == "RUNNING" and containers_ready:
                break
            if status in {"FAILED", "INTERNAL_ERROR"}:
                break
        finally:
            cursor.close()
        time.sleep(10)

    cursor = connection.cursor(snowflake.connector.DictCursor)
    try:
        cursor.execute(f"SHOW ENDPOINTS IN SERVICE {DATABASE}.{SCHEMA}.{SERVICE}")
        endpoints = [
            {key.lower(): value for key, value in row.items()}
            for row in cursor.fetchall()
        ]
    finally:
        cursor.close()
    return {
        "status": status,
        "containers": containers,
        "endpoints": endpoints,
    }


def deploy(
    connection_name: str,
    tag: str,
    planner_users: str,
    approver_users: str,
    wait_seconds: int,
    podman_machine: str,
) -> dict[str, Any]:
    planner_set = {item.strip().upper() for item in planner_users.split(",") if item.strip()}
    approver_set = {item.strip().upper() for item in approver_users.split(",") if item.strip()}
    if not planner_set or not approver_set:
        raise ValueError("At least one planner and one approver Snowflake user are required.")
    overlap = planner_set & approver_set
    if overlap:
        raise ValueError(
            "Planner and approver memberships must be separate Snowflake users; "
            f"overlap: {', '.join(sorted(overlap))}."
        )
    snow_binary = shutil.which("snow")
    podman_binary = shutil.which("podman")
    if not snow_binary:
        raise RuntimeError("Snowflake CLI is required. Install the official snowflake-cli package.")
    if not podman_binary:
        raise RuntimeError("Podman is required to build Linux AMD64 images.")
    builder_architecture = _ensure_podman(podman_binary, podman_machine)

    connection = snowflake.connector.connect(connection_name=connection_name)
    try:
        foundation_query_ids = _execute_file(
            connection,
            ROOT / "snowflake/hosting/001_spcs_foundation.sql",
        )
        repository_url = _repository_url(connection)
    finally:
        connection.close()

    authfile = _registry_login(snow_binary, connection_name)

    images = {
        "api": f"{repository_url}/supplychain-api:{tag}",
        "web": f"{repository_url}/supplychain-web:{tag}",
    }
    for name, dockerfile in (("api", "deploy/spcs/backend.Dockerfile"), ("web", "deploy/spcs/frontend.Dockerfile")):
        build_command = [
            podman_binary,
            "build",
            "--platform",
            "linux/amd64",
            "--file",
            dockerfile,
            "--tag",
            images[name],
        ]
        if name == "web":
            build_command.extend(
                ["--build-arg", f"BUILDPLATFORM=linux/{builder_architecture}"]
            )
        build_command.append(".")
        _run(build_command)
        _run([podman_binary, "push", "--authfile", str(authfile), images[name]])

    spec = _render_spec(tag, planner_users, approver_users)
    connection = snowflake.connector.connect(connection_name=connection_name)
    try:
        deploy_query_id = _deploy_service(connection, spec)
        evidence = _service_evidence(connection, wait_seconds)
    finally:
        connection.close()

    return {
        "status": "PASS" if evidence["status"] == "RUNNING" else evidence["status"],
        "image_tag": tag,
        "images": images,
        "foundation_query_ids": foundation_query_ids,
        "service_deploy_query_id": deploy_query_id,
        **evidence,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Build, publish, and deploy the application to Snowpark Container Services."
    )
    parser.add_argument("--connection", default="supplychain-hackathon-admin")
    parser.add_argument(
        "--tag",
        default=datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
    )
    parser.add_argument("--planner-users", required=True)
    parser.add_argument("--approver-users", required=True)
    parser.add_argument("--wait-seconds", type=int, default=900)
    parser.add_argument("--podman-machine", default="podman-machine-default")
    args = parser.parse_args()
    print(
        json.dumps(
            deploy(
                args.connection,
                args.tag,
                args.planner_users,
                args.approver_users,
                args.wait_seconds,
                args.podman_machine,
            ),
            indent=2,
            default=str,
        )
    )


if __name__ == "__main__":
    main()
