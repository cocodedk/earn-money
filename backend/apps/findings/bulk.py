"""Bulk-create helper for `Finding` rows that ALSO fires post_save.

Django's `Model.objects.bulk_create` is fast but doesn't run signals —
which means the `FINDING_CREATED` post_save hook in `signals.py` never
fires for stubs that batch their inserts. This helper closes the gap:
bulk-insert in one round-trip, then re-emit `post_save(created=True)`
for each inserted row so the standard signal pipeline runs uniformly
whether a stub saves one finding or twenty.

Use this from every stub runner instead of `Finding.objects.bulk_create`.
"""
from __future__ import annotations

from django.db.models.signals import post_save

from .models import Finding


def bulk_create_findings(findings: list[Finding]) -> list[Finding]:
    """Bulk insert + per-row post_save emit. Caller must wrap in
    `transaction.atomic()` so the inserts and resulting Events land
    together. Returns the inserted rows (matching `bulk_create`)."""
    created = Finding.objects.bulk_create(findings)
    for f in created:
        post_save.send(sender=Finding, instance=f, created=True)
    return created
