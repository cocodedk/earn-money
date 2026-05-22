# Task 08a — Stub 2.14: mutation generation (test_mutate.py + mutate.py)

**Part of:** Task 08 — Stub 2.14: oauth-redirect-uri detection chain

**Files:**
- Create: `backend/apps/stubs/oauth_redirect_uri/tests/test_mutate.py`
- Create: `backend/apps/stubs/oauth_redirect_uri/mutate.py`

**Depends on:** Task 03, Task 06

**Continues in:** [08b-classify.md](08b-classify.md)

---

- [ ] **Step 1: Write failing tests for `mutate.py`**

`backend/apps/stubs/oauth_redirect_uri/tests/test_mutate.py`:

```python
"""Unit tests for stub 2.14 redirect URI mutation generation."""
from __future__ import annotations
import pytest
from apps.stubs.oauth_redirect_uri.mutate import generate_mutations, MutationClass


VALID = "https://app.example.test/oauth/callback"
SCANNER = "https://scanner.invalid"


def test_generates_all_mutation_classes():
    mutations = generate_mutations(VALID, SCANNER)
    classes = {m.mutation_class for m in mutations}
    assert MutationClass.FOREIGN_ORIGIN in classes
    assert MutationClass.HOST_SUFFIX in classes
    assert MutationClass.HOST_PREFIX in classes
    assert MutationClass.SCHEME_DOWNGRADE in classes
    assert MutationClass.PATH_PREFIX in classes
    assert MutationClass.PATH_TRAVERSAL in classes
    assert MutationClass.ENCODED_HOST in classes
    assert MutationClass.USERINFO_CONFUSION in classes


def test_count_respects_cap():
    mutations = generate_mutations(VALID, SCANNER, max_probes=4)
    assert len(mutations) <= 4


def test_foreign_origin_uses_scanner_origin():
    mutations = generate_mutations(VALID, SCANNER)
    foreign = next(m for m in mutations if m.mutation_class == MutationClass.FOREIGN_ORIGIN)
    from urllib.parse import urlparse
    assert urlparse(foreign.mutated_uri).netloc == "scanner.invalid"


def test_scheme_downgrade_uses_http():
    mutations = generate_mutations(VALID, SCANNER)
    downgrade = next(m for m in mutations if m.mutation_class == MutationClass.SCHEME_DOWNGRADE)
    assert downgrade.mutated_uri.startswith("http://")


def test_mutations_preserve_state():
    mutations = generate_mutations(VALID, SCANNER)
    for m in mutations:
        assert m.mutation_class is not None
        assert m.mutated_uri


def test_invalid_baseline_returns_empty():
    mutations = generate_mutations("not-a-url", SCANNER)
    assert mutations == []
```

- [ ] **Step 2: Run — verify FAIL**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/tests/test_mutate.py -v 2>&1 | grep -E "FAILED|ERROR|ImportError"
```

- [ ] **Step 3: Write `mutate.py`**

```python
"""Stub 2.14 — redirect URI mutation generation."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal
from urllib.parse import urlparse


class MutationClass(str, Enum):
    FOREIGN_ORIGIN = "foreign_origin"
    HOST_SUFFIX = "host_suffix"
    HOST_PREFIX = "host_prefix"
    SCHEME_DOWNGRADE = "scheme_downgrade"
    PATH_PREFIX = "path_prefix"
    PATH_TRAVERSAL = "path_traversal"
    ENCODED_HOST = "encoded_host"
    USERINFO_CONFUSION = "userinfo_confusion"


@dataclass(frozen=True)
class RedirectUriMutation:
    mutation_class: MutationClass
    mutated_uri: str
    baseline_uri: str
    scanner_origin: str


def generate_mutations(
    baseline_redirect_uri: str,
    scanner_origin: str,
    max_probes: int = 8,
) -> list[RedirectUriMutation]:
    """Generate at most `max_probes` mutated redirect URIs from `baseline_redirect_uri`."""
    try:
        b = urlparse(baseline_redirect_uri)
        s = urlparse(scanner_origin)
    except Exception:
        return []

    if not b.netloc or not s.netloc:
        return []

    scanner_host = s.netloc
    trusted_host = b.netloc
    trusted_path = b.path or "/oauth/callback"

    candidates: list[tuple[MutationClass, str]] = [
        (MutationClass.FOREIGN_ORIGIN,
         f"{scanner_origin}{trusted_path}"),
        (MutationClass.HOST_SUFFIX,
         f"{b.scheme}://{trusted_host}.{scanner_host}{trusted_path}"),
        (MutationClass.HOST_PREFIX,
         f"{b.scheme}://{scanner_host}.{trusted_host}{trusted_path}"),
        (MutationClass.SCHEME_DOWNGRADE,
         f"http://{trusted_host}{trusted_path}"),
        (MutationClass.PATH_PREFIX,
         f"{b.scheme}://{trusted_host}{trusted_path}.evil"),
        (MutationClass.PATH_TRAVERSAL,
         f"{b.scheme}://{trusted_host}{trusted_path}/../evil"),
        (MutationClass.ENCODED_HOST,
         f"{b.scheme}://{trusted_host.replace('.', '%2e')}.{scanner_host}{trusted_path}"),
        (MutationClass.USERINFO_CONFUSION,
         f"{b.scheme}://{trusted_host}@{scanner_host}{trusted_path}"),
    ]

    return [
        RedirectUriMutation(
            mutation_class=cls,
            mutated_uri=uri,
            baseline_uri=baseline_redirect_uri,
            scanner_origin=scanner_origin,
        )
        for cls, uri in candidates[:max_probes]
    ]
```

- [ ] **Step 4: Run mutate tests — verify PASS**

```bash
cd backend && python -m pytest apps/stubs/oauth_redirect_uri/tests/test_mutate.py -v
```

**Continues in:** [08b-classify.md](08b-classify.md)
