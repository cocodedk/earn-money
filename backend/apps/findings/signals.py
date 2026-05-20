"""Finding lifecycle signals.

`FINDING_CREATED` Events are emitted from a single `post_save` hook
rather than per-stub at every emit-site. Each finding-creating stub
gets the event for free; future stubs inherit it automatically.

The hook only fires on FIRST save (`created=True`). Subsequent saves
that flip `status` go through the existing `FINDING_STATUS_CHANGED`
emit-path (see [[project-event-log-medium-done-well]]).
"""
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.events.models import Event
from apps.events.types import EventType

from .models import Finding


@receiver(post_save, sender=Finding)
def _emit_finding_created(
    sender, instance: Finding, created: bool, **_kwargs,
) -> None:
    if not created:
        return
    Event.log(
        type=EventType.FINDING_CREATED,
        scan_run=instance.scan_run,
        target=instance.target,
        subject=instance,
        data={
            "id": str(instance.id),
            "stub_slug": instance.stub_slug,
            "category": instance.category,
            "severity": instance.severity,
            "confidence": instance.confidence,
            "status": instance.status,
        },
    )
