from __future__ import annotations

from pathlib import Path

import pytest

from earn_money import db
from earn_money.recon import runs, signals
from earn_money.recon.signals import Signal
from earn_money.triage import findings, verify_takeover_cli
from tests.triage.conftest import engine_paths, make_finding


def _insert_takeover(
    paths: object,
    finding_hash: str,
    *,
    vuln_class: str = "github-takeover",
    extracted: str = "someorg.github.io",
) -> None:
    """Seed a takeover signal + its finding into the DB."""
    conn = db.open_db(paths.program_db("hackerone", "example"))  # type: ignore[attr-defined]
    try:
        # Need a recon_runs row + signals row so the CLI can look up the payload.
        runs.start_run(
            conn, run_id="nuclei-takeover-r1", platform="hackerone", slug="example",
            tool="nuclei", started_at="2026-05-14T06:49:00Z",
            artifact_dir="x", input_count=1,
        )
        runs.finish_run(
            conn, run_id="nuclei-takeover-r1",
            finished_at="2026-05-14T06:49:52Z", status="success",
            output_count=1, signal_count=1, source_failures=0, oos_drops=0,
        )
        signals.insert_signals(conn, [Signal(
            run_id="nuclei-takeover-r1", tool="nuclei",
            signal_type="template_match",
            asset="mta-sts.wearehackerone.com",
            target="https://mta-sts.wearehackerone.com/",
            signature=f"{vuln_class}||{extracted}",
            payload=(
                f'{{"template_id":"{vuln_class}","severity":"high",'
                f'"name":"Takeover Detection","extracted":"{extracted}"}}'
            ),
            observed_at="2026-05-14T06:49:52Z",
        )])
        findings.upsert_finding(conn, make_finding(
            finding_hash=finding_hash,
            vuln_class=vuln_class,
            severity_hint="high",
            asset="mta-sts.wearehackerone.com",
            target="https://mta-sts.wearehackerone.com/",
            signature=f"{vuln_class}||{extracted}",
            source_run_id="nuclei-takeover-r1",
            notes_path=f"findings/_queue/{finding_hash}.md",
        ))
    finally:
        conn.close()


def _run(
    root: Path, argv: list[str], capsys: pytest.CaptureFixture[str],
) -> tuple[int, str, str]:
    rc = verify_takeover_cli.main(["--root", str(root), *argv])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_verify_takeover_claimed_org(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str], mocker: pytest.FixtureRequest,
) -> None:
    paths = engine_paths(tmp_repo)
    fh = "f" * 64
    _insert_takeover(paths, fh, extracted="hacker0x01.github.io")
    mocker.patch.object(  # type: ignore[attr-defined]
        verify_takeover_cli, "_github_user_lookup",
        return_value=(200, {
            "login": "Hacker0x01", "type": "Organization",
            "name": "HackerOne", "blog": "https://www.hackerone.com",
        }),
    )
    rc, out, _ = _run(paths.root, ["--program", "example", fh[:8]], capsys)
    assert rc == 0
    assert "CLAIMED" in out
    assert "Hacker0x01" in out
    assert "Organization" in out
    assert "resolved_na" in out  # recommended action


def test_verify_takeover_unclaimed(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str], mocker: pytest.FixtureRequest,
) -> None:
    paths = engine_paths(tmp_repo)
    fh = "e" * 64
    _insert_takeover(paths, fh, extracted="never-existed-org.github.io")
    mocker.patch.object(  # type: ignore[attr-defined]
        verify_takeover_cli, "_github_user_lookup",
        return_value=(404, {}),
    )
    rc, out, _ = _run(paths.root, ["--program", "example", fh[:8]], capsys)
    assert rc == 0
    assert "UNCLAIMED" in out
    assert "never-existed-org" in out
    assert "verified" in out.lower()  # recommend escalation


def test_verify_takeover_indeterminate(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str], mocker: pytest.FixtureRequest,
) -> None:
    paths = engine_paths(tmp_repo)
    fh = "d" * 64
    _insert_takeover(paths, fh, extracted="anything.github.io")
    mocker.patch.object(  # type: ignore[attr-defined]
        verify_takeover_cli, "_github_user_lookup",
        return_value=(0, {}),  # 0 = network error in our convention
    )
    rc, out, _ = _run(paths.root, ["--program", "example", fh[:8]], capsys)
    assert rc == 0
    assert "INDETERMINATE" in out


def test_verify_takeover_rate_limited(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str], mocker: pytest.FixtureRequest,
) -> None:
    """GitHub returns 403 with X-RateLimit-Remaining=0 → INDETERMINATE."""
    paths = engine_paths(tmp_repo)
    fh = "9" * 64
    _insert_takeover(paths, fh, extracted="some-org.github.io")
    mocker.patch.object(  # type: ignore[attr-defined]
        verify_takeover_cli, "_github_user_lookup",
        return_value=(429, {"error": "GitHub API rate limit exhausted"}),
    )
    rc, out, _ = _run(paths.root, ["--program", "example", fh[:8]], capsys)
    assert rc == 0
    assert "INDETERMINATE" in out


def test_verify_takeover_refuses_non_takeover_finding(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    fh = "c" * 64
    _insert_takeover(paths, fh, vuln_class="csp-script-src-wildcard")
    rc, _, err = _run(paths.root, ["--program", "example", fh[:8]], capsys)
    assert rc == 1
    assert "not a takeover" in err.lower()


def test_verify_takeover_unknown_prefix_returns_1(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    rc, _, err = _run(paths.root, ["--program", "example", "deadbeef"], capsys)
    assert rc == 1
    assert "no finding" in err.lower()


def test_verify_takeover_unregistered_program_returns_1(
    tmp_repo: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    paths = engine_paths(tmp_repo)
    rc, _, err = _run(paths.root, ["--program", "does-not-exist", "deadbeef"], capsys)
    assert rc == 1
    assert "not registered" in err.lower()
