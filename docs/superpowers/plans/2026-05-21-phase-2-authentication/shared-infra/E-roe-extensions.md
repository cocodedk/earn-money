# Slice E — RoE extensions for Phase 2 gating

> Lives in `backend/apps/programs/roe.py` (extends existing `RoE` dataclass).

## What changes

Five new boolean fields on `RoE`, all default `False`:

```python
@dataclass(frozen=True)
class RoE:
    max_requests_per_second: int
    dos_authorized: bool = False
    destructive_payloads_authorized: bool = False
    social_engineering_authorized: bool = False
    pii_handling: str = "synthetic_data_only"
    authorized_test_environments: list[str] = field(default_factory=list)
    authorized_test_accounts: list[str] = field(default_factory=list)
    special_notes: str = ""
    # NEW — Phase 2 active-probe gates
    allow_active_login_probes: bool = False
    allow_password_reset_probes: bool = False
    allow_mfa_probes: bool = False
    allow_oauth_probes: bool = False
    allow_registration_probes: bool = False
```

## Why on the existing dataclass, not a new one

The RoE dataclass IS the per-program contract. Adding new auth-specific
RoE knobs to it keeps one source of truth. A separate `AuthRoE` would
fork the contract and risk drift.

## Parse contract

`loader._parse_roe` accepts the new fields:

* If a roe.md frontmatter omits a knob, it stays `False` (operator
  default-deny).
* If a roe.md sets a knob to a non-bool, parse raises `InvalidRoE`.
* Unknown additional fields in roe.md are ignored (forward-compat).

## Existing-program migration

Programs registered before Phase 2 lands:

* `programs/hackerone/algolia/roe.md` — operator updates to add the
  five knobs explicitly. Default `False` for all five (algolia hasn't
  authorised any active probing).
* `programs/local/juice-shop/roe.md` — operator sets all five to
  `True` (fixture target, full auth-flow exercise authorised).
* `programs/local/dvwa/roe.md` — same.
* `programs/local/webgoat/roe.md` — same.

## Why default-deny instead of default-passive

CLAUDE.md's three-tier policy says `manual-only` programs refuse all
active stubs. Setting the new knobs default-`True` would make every
`rate-limited-OK` program *implicitly* authorise active auth probing,
which is wrong — `rate-limited-OK` means "you may scan in line with
our rate limits", not "you may submit forms". The operator must opt in
per-program.

## Tests

* Default RoE has all five knobs `False`.
* `_parse_roe` reads `allow_active_login_probes: true` correctly.
* `_parse_roe` raises `InvalidRoE` on non-bool input for any knob.
* Existing roe.md files with no new fields still parse and have
  knobs default `False`.
* Backward compatibility: every Phase 1 test that constructs RoE
  inline still works (defaults cover the new fields).
