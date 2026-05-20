from __future__ import annotations

import threading
import time
from pathlib import Path

from earn_money import config
from earn_money.runners import watchdog


def test_watchdog_fires_when_recon_disabled(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    fired = threading.Event()
    reason_holder: dict[str, str | None] = {"reason": None}

    def on_state_change(reason: str) -> None:
        reason_holder["reason"] = reason
        fired.set()

    wd = watchdog.KillSwitchWatchdog(
        paths, platform="hackerone", slug="example",
        on_state_change=on_state_change, poll_interval_s=0.05,
    )
    wd.start()
    try:
        paths.recon_enabled_flag.unlink()
        assert fired.wait(timeout=1.0), "watchdog never fired"
        assert reason_holder["reason"] == "kill_switch"
    finally:
        wd.stop()


def test_watchdog_fires_when_program_frozen(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    fired = threading.Event()
    reason_holder: dict[str, str | None] = {"reason": None}

    def on_state_change(reason: str) -> None:
        reason_holder["reason"] = reason
        fired.set()

    wd = watchdog.KillSwitchWatchdog(
        paths, platform="hackerone", slug="example",
        on_state_change=on_state_change, poll_interval_s=0.05,
    )
    wd.start()
    try:
        paths.program_dir("hackerone", "example").mkdir(parents=True, exist_ok=True)
        (paths.program_dir("hackerone", "example") / "FROZEN").write_text("test")
        assert fired.wait(timeout=1.0), "watchdog never fired"
        assert reason_holder["reason"] == "freeze"
    finally:
        wd.stop()


def test_watchdog_does_not_fire_when_state_stable(tmp_repo: Path) -> None:
    paths = config.Paths.from_root(tmp_repo)
    paths.recon_enabled_flag.touch()
    fired = threading.Event()

    wd = watchdog.KillSwitchWatchdog(
        paths, platform="hackerone", slug="example",
        on_state_change=lambda _: fired.set(),
        poll_interval_s=0.05,
    )
    wd.start()
    try:
        time.sleep(0.3)
        assert not fired.is_set()
    finally:
        wd.stop()
