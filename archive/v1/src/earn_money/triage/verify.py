"""Promote a finding to verified and auto-generate its skeleton draft."""
from __future__ import annotations

import logging
from pathlib import Path
from sqlite3 import Connection

from earn_money import config
from earn_money.triage.draft import DraftAlreadyExists, TemplateNotFound, draft_for
from earn_money.triage.history import transition_state

_log = logging.getLogger(__name__)


def promote(
    conn: Connection,
    paths: config.Paths,
    *,
    platform: str,
    slug: str,
    finding_hash: str,
    actor: str,
    note: str | None,
    now: str,
) -> Path | None:
    """Transition to 'verified' and write the skeleton draft.

    Returns the draft path, or None if the draft could not be written.
    The state transition is never rolled back on draft failure.
    """
    transition_state(
        conn,
        finding_hash=finding_hash,
        to_state="verified",
        actor=actor,
        note=note,
        now=now,
    )
    try:
        return draft_for(
            paths, platform=platform, slug=slug, finding_hash=finding_hash
        )
    except (TemplateNotFound, DraftAlreadyExists) as exc:
        _log.warning("promote: skipping draft for %s: %s", finding_hash[:8], exc)
        return None
