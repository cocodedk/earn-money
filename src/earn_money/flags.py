"""Operational safety flags: kill-switch and per-program freeze."""

from __future__ import annotations

from datetime import UTC, datetime

from earn_money.config import Paths


class ReconDisabled(Exception):
    """Raised when RECON_ENABLED flag is absent."""


class ProgramFrozen(Exception):
    """Raised when a program has an active FROZEN flag."""


def require_recon_enabled(paths: Paths) -> None:
    if not paths.recon_enabled_flag.exists():
        raise ReconDisabled(
            f"RECON_ENABLED flag absent at {paths.recon_enabled_flag}. "
            "Create the file to enable recon; remove it to halt."
        )


def is_program_frozen(paths: Paths, platform: str, slug: str) -> bool:
    return paths.freeze_flag(platform, slug).exists()


def freeze_program(paths: Paths, platform: str, slug: str, *, reason: str) -> None:
    flag = paths.freeze_flag(platform, slug)
    flag.parent.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).isoformat(timespec="seconds")
    flag.write_text(f"{timestamp}\n{reason}\n", encoding="utf-8")


def unfreeze_program(paths: Paths, platform: str, slug: str) -> None:
    flag = paths.freeze_flag(platform, slug)
    if flag.exists():
        flag.unlink()


def freeze_reason(paths: Paths, platform: str, slug: str) -> str:
    flag = paths.freeze_flag(platform, slug)
    return flag.read_text(encoding="utf-8") if flag.exists() else ""


def require_program_not_frozen(paths: Paths, platform: str, slug: str) -> None:
    reason = freeze_reason(paths, platform, slug)
    if reason:
        raise ProgramFrozen(
            f"Program {platform}/{slug} is frozen.\n{reason.strip()}\n"
            "Resolve the underlying issue and remove the FROZEN file to resume."
        )
