"""Roles and organisation isolation (no login system: see the owner decision
in docs/AI_USAGE_INTELLIGENCE.md).

Roles, narrowest first:
  demo_viewer   the public: demonstration dataset ONLY, never live data
  member        own events only (user_id)
  team_lead     own team (team_id) within own org
  org_admin     whole own organisation
  owner         platform owner: all organisations, live data, data entry

Every live query goes through scope(): it filters to what the principal may
see BEFORE any aggregation, so a total can never include data the viewer
is not allowed to see. Requested filters outside the principal's scope are
refused (403), not silently widened or narrowed.
"""
from __future__ import annotations

import dataclasses

ROLES = ("demo_viewer", "member", "team_lead", "org_admin", "owner")


class Forbidden(Exception):
    pass


@dataclasses.dataclass(frozen=True)
class Principal:
    role: str
    user_id: str | None = None
    team_id: str | None = None
    org_id: str | None = None

    def __post_init__(self):
        if self.role not in ROLES:
            raise ValueError(f"unknown role {self.role!r}")

    @property
    def may_see_live(self) -> bool:
        return self.role != "demo_viewer"

    @property
    def may_write(self) -> bool:
        return self.role in ("org_admin", "owner")


def allowed(principal: Principal, row) -> bool:
    org, team, user = getattr(row, "org_id", None), getattr(row, "team_id", None), getattr(row, "user_id", None)
    dataset = getattr(row, "dataset", "live")
    if principal.role == "demo_viewer":
        return dataset == "demo"
    if dataset == "demo":
        return False  # live views never mix in demo rows
    if principal.role == "owner":
        return True
    if org != principal.org_id:
        return False
    if principal.role == "org_admin":
        return True
    if principal.role == "team_lead":
        return team == principal.team_id
    return user == principal.user_id  # member


def scope(principal: Principal, rows: list) -> list:
    return [r for r in rows if allowed(principal, r)]


def check_filters(principal: Principal, *, org_id=None, team_id=None, user_id=None) -> None:
    """Refuse a filter that asks for data outside the principal's scope."""
    if principal.role in ("owner", "demo_viewer"):
        return
    if org_id and org_id != principal.org_id:
        raise Forbidden("organisation outside your scope")
    if principal.role == "team_lead" and team_id and team_id != principal.team_id:
        raise Forbidden("team outside your scope")
    if principal.role == "member" and ((team_id and team_id != principal.team_id) or (user_id and user_id != principal.user_id)):
        raise Forbidden("members can only see their own usage")
