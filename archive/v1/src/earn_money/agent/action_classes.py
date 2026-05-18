"""Probe action classes + STOP-validation scaffolding.

The engine groups concrete LLM actions into a small set of "classes" so
the loop can:

- track which classes have been tried this run
- compute which classes are still applicable (have a real reason to fire
  given the evidence so far) AND allowed by RoE
- reject a premature STOP when applicable classes remain untried

Classes are deliberately coarse — the LLM still picks the exact action;
the engine just makes sure the LLM doesn't quit before exploring all
escalation lanes that are actually relevant.
"""
from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import TYPE_CHECKING

from earn_money.agent.probe_actions import (
    GetAction,
    PostAction,
    ReportCandidateAction,
    SetHeaderAction,
    StopAction,
    StoreAction,
)

if TYPE_CHECKING:
    from earn_money.agent.hacker_session import HackerSession
    from earn_money.agent.observations import ObservationWrapper
    from earn_money.agent.roe_profile import RoeProfile


class ActionClass(StrEnum):
    """Coarse-grained probe action categories.

    `report_or_stop` is intentionally NOT in this enum — STOP is the
    terminal action and shouldn't be bookkept as a probe class.
    """

    DISCOVERY_GET     = "discovery_get"      # /, /robots.txt, /sitemap.xml, top-level
    CLIENT_ANALYSIS   = "client_analysis"    # GET *.js / static bundle inspection
    API_ENUMERATION   = "api_enumeration"    # GET /api/*, /rest/*
    AUTH_DISCOVERY    = "auth_discovery"     # login/register/session/password-reset routes
    POST_PROBE        = "post_probe"         # POST to known endpoints (non-auth)
    HEADER_PROBE      = "header_probe"       # set_header / cookie / content-type variations


_DISCOVERY_PATHS = frozenset({
    "/", "/robots.txt", "/sitemap.xml", "/favicon.ico",
    "/index.html", "/.well-known/security.txt",
})

_AUTH_KEYWORDS = ("login", "register", "signin", "signup", "session", "auth", "password")


def _is_auth_path(path: str) -> bool:
    lower = path.lower()
    return any(kw in lower for kw in _AUTH_KEYWORDS)


def _is_api_path(path: str) -> bool:
    lower = path.lower()
    return "/api/" in lower or "/rest/" in lower or lower in ("/api", "/rest")


def classify_action(action: object) -> ActionClass | None:
    """Map a concrete action to its class.

    Returns None for actions that aren't probe classes (StoreAction,
    ReportCandidateAction, StopAction).
    """
    if isinstance(action, GetAction):
        path = action.args.path
        if _is_auth_path(path):
            return ActionClass.AUTH_DISCOVERY
        if path.endswith(".js") or path.endswith(".mjs"):
            return ActionClass.CLIENT_ANALYSIS
        if _is_api_path(path):
            return ActionClass.API_ENUMERATION
        return ActionClass.DISCOVERY_GET

    if isinstance(action, PostAction):
        if _is_auth_path(action.args.path):
            return ActionClass.AUTH_DISCOVERY
        return ActionClass.POST_PROBE

    if isinstance(action, SetHeaderAction):
        return ActionClass.HEADER_PROBE

    if isinstance(action, (StoreAction, ReportCandidateAction, StopAction)):
        return None

    return None


# ── applicability ──────────────────────────────────────────────────────


def _any_obs_matching(
    session: HackerSession, predicate: Callable[[ObservationWrapper], bool],
) -> bool:
    return any(predicate(obs) for obs in session.observations)


def _any_html_or_js_observed(session: HackerSession) -> bool:
    def is_html_or_js(obs: ObservationWrapper) -> bool:
        ctype = (obs.headers.get("content-type") or "").lower()
        return "html" in ctype or "javascript" in ctype
    return _any_obs_matching(session, is_html_or_js)


def _any_api_observed(session: HackerSession) -> bool:
    return _any_obs_matching(session, lambda obs: _is_api_path(obs.final_url or ""))


def _any_auth_boundary_observed(session: HackerSession) -> bool:
    return _any_obs_matching(session, lambda obs: obs.status in (401, 403))


def untried_applicable_classes(
    session: HackerSession, roe: RoeProfile, tried: set[ActionClass],
) -> set[ActionClass]:
    """Classes that are (a) not yet tried, (b) allowed by RoE, and
    (c) applicable given the evidence the session has accumulated.

    "Applicable" is the key distinction: RoE may allow POST, but if the
    engine has not yet discovered any endpoints, `post_probe` is not
    applicable. STOP rejection consults this set, not the broader "any
    allowed class" set.
    """
    applicable: set[ActionClass] = set()

    # discovery_get — always applicable until tried
    if ActionClass.DISCOVERY_GET not in tried and roe.allow_get:
        applicable.add(ActionClass.DISCOVERY_GET)

    # auth_discovery — always applicable until tried (every target is presumed
    # to have an auth surface worth probing once)
    if ActionClass.AUTH_DISCOVERY not in tried:
        get_ok = roe.allow_get
        post_ok = roe.allow_post
        if get_ok or post_ok:
            applicable.add(ActionClass.AUTH_DISCOVERY)

    # client_analysis — applicable only after observing HTML or JS responses
    if (
        ActionClass.CLIENT_ANALYSIS not in tried
        and roe.allow_get
        and _any_html_or_js_observed(session)
    ):
        applicable.add(ActionClass.CLIENT_ANALYSIS)

    # api_enumeration — applicable only after observing some /api/* or /rest/*
    # response (or never, if recon hasn't surfaced any API surface yet)
    if (
        ActionClass.API_ENUMERATION not in tried
        and roe.allow_get
        and _any_api_observed(session)
    ):
        applicable.add(ActionClass.API_ENUMERATION)

    # post_probe — applicable only when RoE allows POST AND endpoints exist
    if (
        ActionClass.POST_PROBE not in tried
        and roe.allow_post
        and (_any_api_observed(session) or _any_html_or_js_observed(session))
    ):
        applicable.add(ActionClass.POST_PROBE)

    # header_probe — applicable after an auth boundary (401/403) has been seen
    if (
        ActionClass.HEADER_PROBE not in tried
        and _any_auth_boundary_observed(session)
    ):
        applicable.add(ActionClass.HEADER_PROBE)

    return applicable
