from __future__ import annotations

from dataclasses import dataclass
import os

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Identity:
    actor_id: str
    display_name: str
    title: str
    roles: frozenset[str]
    identity_source: str = "ALLOWLISTED_DEMO_PRINCIPAL"

    def public(self) -> dict[str, object]:
        return {
            "actor_id": self.actor_id,
            "display_name": self.display_name,
            "title": self.title,
            "roles": sorted(self.roles),
            "identity_source": self.identity_source,
        }


IDENTITIES = {
    "maya.iyer": Identity(
        actor_id="maya.iyer",
        display_name="Maya Iyer",
        title="Supply Planning",
        roles=frozenset({"ANALYST", "SUPPLY_PLANNER"}),
    ),
    "aisha.rao": Identity(
        actor_id="aisha.rao",
        display_name="Aisha Rao",
        title="VP Operations",
        roles=frozenset({"ANALYST", "MITIGATION_APPROVER"}),
    ),
}

ANONYMOUS = Identity(
    actor_id="anonymous",
    display_name="Read-only analyst",
    title="Unauthenticated",
    roles=frozenset({"ANALYST"}),
)


def resolve_identity(request: Request) -> Identity:
    """Resolve a trusted Snowflake ingress user or a local demo principal.

    Snowpark Container Services injects Sf-Context-Current-User after its
    public-endpoint authentication gate. Local mode retains two allowlisted
    principals so the separation-of-duties flow can be tested offline.
    """

    identity_mode = os.getenv("SUPPLYCHAIN_IDENTITY_MODE", "demo").strip().lower()
    if identity_mode == "spcs":
        snowflake_user = request.headers.get("Sf-Context-Current-User", "").strip().upper()
        if not snowflake_user:
            raise HTTPException(
                status_code=401,
                detail="Snowflake ingress identity is required.",
            )

        def configured_users(variable: str) -> set[str]:
            return {
                value.strip().upper()
                for value in os.getenv(variable, "").split(",")
                if value.strip()
            }

        roles = {"ANALYST"}
        if snowflake_user in configured_users("SUPPLYCHAIN_PLANNER_USERS"):
            roles.add("SUPPLY_PLANNER")
        if snowflake_user in configured_users("SUPPLYCHAIN_APPROVER_USERS"):
            roles.add("MITIGATION_APPROVER")
        title = (
            "Supply planner and mitigation approver"
            if {"SUPPLY_PLANNER", "MITIGATION_APPROVER"}.issubset(roles)
            else "Supply planner"
            if "SUPPLY_PLANNER" in roles
            else "Mitigation approver"
            if "MITIGATION_APPROVER" in roles
            else "Read-only analyst"
        )
        return Identity(
            actor_id=snowflake_user.lower(),
            display_name=snowflake_user,
            title=title,
            roles=frozenset(roles),
            identity_source="SNOWFLAKE_SPCS_INGRESS",
        )

    if identity_mode != "demo":
        raise RuntimeError("SUPPLYCHAIN_IDENTITY_MODE must be either 'demo' or 'spcs'.")

    actor_id = request.headers.get("X-Demo-Actor", "").strip().lower()
    if not actor_id:
        return ANONYMOUS
    identity = IDENTITIES.get(actor_id)
    if not identity:
        raise HTTPException(status_code=401, detail="Unknown demo principal.")
    return identity


def require_role(identity: Identity, role: str) -> None:
    if role not in identity.roles:
        raise HTTPException(
            status_code=403,
            detail=f"{identity.display_name} is not authorized for role {role}.",
        )


def require_any_role(identity: Identity, *roles: str) -> None:
    if not set(roles).intersection(identity.roles):
        raise HTTPException(
            status_code=403,
            detail=(
                f"{identity.display_name} is not authorized for any required role: "
                f"{', '.join(roles)}."
            ),
        )
