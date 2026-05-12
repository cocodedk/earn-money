"""Background thread that polls RECON_ENABLED and the per-program FROZEN
flag every few seconds during a subprocess. On state change it calls a
kill callback so the wrapper can SIGTERM the in-flight tool."""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Literal

from earn_money import config

Reason = Literal["kill_switch", "freeze"]


class KillSwitchWatchdog:
    """Thread that watches kill-switch + freeze state and fires a callback
    on change. ``start()`` begins polling; ``stop()`` joins cleanly. The
    callback is fired at most once per watchdog lifetime."""

    def __init__(
        self,
        paths: config.Paths,
        *,
        platform: str,
        slug: str,
        on_state_change: Callable[[Reason], None],
        poll_interval_s: float = 5.0,
    ) -> None:
        self._paths = paths
        self._platform = platform
        self._slug = slug
        self._on_state_change = on_state_change
        self._poll_interval = poll_interval_s
        self._stop = threading.Event()
        self._fired = False
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _frozen(self) -> bool:
        freeze_path = self._paths.program_dir(self._platform, self._slug) / "FROZEN"
        return freeze_path.exists()

    def _recon_enabled(self) -> bool:
        return self._paths.recon_enabled_flag.exists()

    def _run(self) -> None:
        while not self._stop.is_set():
            if self._fired:
                return
            if not self._recon_enabled():
                self._fire("kill_switch")
                return
            if self._frozen():
                self._fire("freeze")
                return
            self._stop.wait(self._poll_interval)

    def _fire(self, reason: Reason) -> None:
        if self._fired:
            return
        self._fired = True
        self._on_state_change(reason)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._thread.join(timeout=self._poll_interval * 2)
