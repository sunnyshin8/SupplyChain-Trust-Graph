from __future__ import annotations

from dataclasses import dataclass

from fastapi import HTTPException, Request


@dataclass(frozen=True)
class Identity:
    actor_id: str
    display_name: str
    title: str
    roles: frozenset[str]

    def public(self) -> dict[str, object]:
        return {
            "actor_id": self.actor_id,
            "display_name": self.display_name,
            "title": self.title,
            "roles": sorted(self.roles),
            "identity_source": "ALLOWLISTED_DEMO_PRINCIPAL",
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
    """Resolve a demo principal from a strict server-side allowlist.

    The header is intentionally a local hackathon identity-provider seam. A
    production deployment must replace it with verified SSO/JWT claims while
    keeping the role checks below unchanged.
    """

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
