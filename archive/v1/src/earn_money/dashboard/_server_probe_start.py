"""POST /api/probe/start orchestration: flag check + slot install +
runner construction.

Extracted from server.py to keep the main module under the project's
200-line file cap. The per-field validators live in
_server_probe_validate.py; this module composes them and installs the
runner into the server's slot.
"""
from __future__ import annotations

import logging
import threading
from typing import Any

from earn_money import config, flags
from earn_money.dashboard.probe_runner import ProbeRunner

from ._server_probe_validate import (
    Responder,
    parse_request_body,
    resolve_roe_path,
    validate_base_url,
    validate_max_turns,
    validate_target,
)

log = logging.getLogger(__name__)


def install_runner(
    runner: ProbeRunner,
    slot_lock: threading.Lock,
    get_slot: Any,
    set_slot: Any,
    r: Responder,
) -> bool:
    """Re-check + install runner under the slot lock. A racing handler
    may have installed its own slot while we were constructing — discard
    ours in that case (it never started; nothing to stop)."""
    with slot_lock:
        current = get_slot()
        if current is not None and current.is_running():
            r.send_json(409, {
                "error": "another probe is running",
                "run_id": current.run_id(),
            })
            return False
        # Install BEFORE starting — otherwise a fast runner can finish
        # before this handler reaches the assignment.
        set_slot(runner)
        try:
            run_id = runner.start()
        except Exception:
            set_slot(None)
            raise
    r.send_json(200, {"run_id": run_id})
    return True


def check_flags_and_freeze(
    paths: config.Paths, target_kind: str, platform: str, program: str | None,
    r: Responder,
) -> bool:
    try:
        flags.require_recon_enabled(paths)
        if target_kind == "registered_program":
            flags.require_program_not_frozen(paths, platform, program)  # type: ignore[arg-type]
    except flags.ReconDisabled as e:
        r.send_json(403, {"error": str(e)})
        return False
    except flags.ProgramFrozen as e:
        r.send_json(403, {"error": str(e)})
        return False
    return True


def handle_probe_start(
    r: Any,
    paths: config.Paths,
    slot_lock: threading.Lock,
    get_slot: Any,
    set_slot: Any,
    *,
    runner_cls: type[ProbeRunner] = ProbeRunner,
) -> None:
    """Orchestrate validation + slot install for POST /api/probe/start.

    Each early-return path emits its own JSON response via the responder;
    this function never returns a body itself. `runner_cls` is taken as
    an arg so tests can swap in a fake runner via
    `patch.object(server, "ProbeRunner", ...)` — the handler factory
    closes over `server.ProbeRunner` lazily and forwards it here.
    """
    body = parse_request_body(r)
    if body is None:
        return
    base_url = validate_base_url(body, r)
    if base_url is None:
        return
    target = validate_target(body, r)
    if target is None:
        return
    target_kind, platform, program = target
    ok, max_turns = validate_max_turns(body, r)
    if not ok:
        return
    roe_path = resolve_roe_path(body, paths)
    if roe_path is not None and not roe_path.exists():
        r.send_json(400, {"error": f"RoE profile not found: {roe_path}"})
        return
    if not check_flags_and_freeze(paths, target_kind, platform, program, r):
        return
    # Fast 409 — fail before doing any construction work.
    with slot_lock:
        current = get_slot()
        if current is not None and current.is_running():
            r.send_json(409, {
                "error": "another probe is running",
                "run_id": current.run_id(),
            })
            return
    # Build the runner OUTSIDE the lock. ProbeRunner.__init__ does file
    # I/O (load_roe_profile), SQLite I/O (_seed_urls), and provider
    # construction (providers_mod.from_env()) — none of which should
    # pin the slot lock across slow operations.
    try:
        runner = runner_cls(
            base_url=base_url, roe_path=roe_path, paths=paths,
            target_kind=target_kind,
            platform=platform, program=program, max_turns=max_turns,
            # NOTE: deliberately no on_finished=. The slot is NOT
            # cleared when the runner exits — that would race a fast
            # run against the browser's EventSource connect (operator
            # never sees the done event). The slot is replaced by the
            # next start instead.
        )
    except Exception:
        log.exception("ProbeRunner init failed")
        r.send_json(500, {"error": "runner init failed"})
        return
    install_runner(runner, slot_lock, get_slot, set_slot, r)
