"""Spec consistency linter — catches stale terms, missing required terms, and
broken paired-term contracts in spec/plan docs.

Usage:
    python scripts/spec_consistency_lint.py <spec.md> <vocab.yaml>

Vocab schema:
    deprecated_terms:
      - pattern: "<regex>"
        message: "<why this is wrong>"
    required_terms:
      - pattern: "<regex>"
        message: "<why this must be present>"
    paired_terms:
      - terms: ["<regex>", "<regex>", ...]
        message: "<why these must appear together>"

Exit codes:
    0 — clean
    1 — violations
    2 — usage / config error
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml


def _load_vocab(vocab_path: Path) -> dict:
    if not vocab_path.exists():
        print(f"ERR vocab file not found: {vocab_path}", file=sys.stderr)
        sys.exit(2)
    return yaml.safe_load(vocab_path.read_text()) or {}


_ALLOW_MARKER = "<!-- lint:allow -->"


def _check_deprecated(lines: list[str], rules: list[dict]) -> list[str]:
    findings: list[str] = []
    for rule in rules:
        pattern = re.compile(rule["pattern"])
        for lineno, line in enumerate(lines, start=1):
            if _ALLOW_MARKER in line:
                continue
            if pattern.search(line):
                findings.append(
                    f"line {lineno}: DEPRECATED {rule['pattern']!r} — "
                    f"{rule['message']}"
                )
    return findings


def _check_required(text: str, rules: list[dict]) -> list[str]:
    findings: list[str] = []
    for rule in rules:
        if not re.search(rule["pattern"], text):
            findings.append(
                f"MISSING required term {rule['pattern']!r} — "
                f"{rule['message']}"
            )
    return findings


def _check_paired(text: str, rules: list[dict]) -> list[str]:
    findings: list[str] = []
    for rule in rules:
        missing = [t for t in rule["terms"] if not re.search(t, text)]
        if missing:
            findings.append(
                f"PAIRED-TERMS missing {missing!r} from group "
                f"{rule['terms']!r} — {rule['message']}"
            )
    return findings


def lint(spec_path: Path, vocab_path: Path) -> int:
    if not spec_path.exists():
        print(f"ERR spec file not found: {spec_path}", file=sys.stderr)
        return 2
    vocab = _load_vocab(vocab_path)
    text = spec_path.read_text()
    lines = text.splitlines()

    findings: list[str] = []
    findings.extend(_check_deprecated(lines, vocab.get("deprecated_terms", [])))
    findings.extend(_check_required(text, vocab.get("required_terms", [])))
    findings.extend(_check_paired(text, vocab.get("paired_terms", [])))

    if findings:
        print(f"FAIL {spec_path} ({len(findings)} finding(s)):")
        for f in findings:
            print(f"  {f}")
        return 1

    print(f"OK {spec_path} — lint clean ({vocab_path.name})")
    return 0


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "Usage: spec_consistency_lint.py <spec.md> <vocab.yaml>",
            file=sys.stderr,
        )
        return 2
    return lint(Path(argv[1]), Path(argv[2]))


if __name__ == "__main__":
    sys.exit(main(sys.argv))
