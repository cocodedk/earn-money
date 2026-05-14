"""Filesystem paths and operational constants."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Paths:
    root: Path
    programs: Path
    recon_outputs: Path
    recon_enabled_flag: Path

    @classmethod
    def from_root(cls, root: Path) -> Paths:
        root = root.resolve()
        return cls(
            root=root,
            programs=root / "programs",
            recon_outputs=root / "recon" / "outputs",
            recon_enabled_flag=root / "RECON_ENABLED",
        )

    def program_dir(self, platform: str, slug: str) -> Path:
        return self.programs / platform / slug

    def scope_file(self, platform: str, slug: str) -> Path:
        return self.program_dir(platform, slug) / "scope.md"

    def roe_file(self, platform: str, slug: str) -> Path:
        return self.program_dir(platform, slug) / "roe.md"

    def freeze_flag(self, platform: str, slug: str) -> Path:
        return self.program_dir(platform, slug) / "FROZEN"

    def program_db(self, platform: str, slug: str) -> Path:
        return self.program_dir(platform, slug) / "db.sqlite"
