---
tier: CAPABLE
depends_on:
  - 03-serializers-turn-session
files:
  creates: []
  modifies:
    - backend/apps/agent/serializers.py
  deletes: []
  renames: []
  generated: []
exports: []
imports:
  - module: "apps.targets.models.ScanTarget"
    file: backend/apps/agent/serializers.py
allow_extra_files: false
---

# Task 5B: Create Serializer — Full Write Logic

Referenced by [05-viewset-create-success.md](05-viewset-create-success.md) Step 3.

**Files:**
- Modify: `backend/apps/agent/serializers.py`

---

Update `AgentSessionSerializer` to support both read and write:

```python
from apps.targets.models import ScanTarget

from .models import AgentPhase, AgentSession, SessionStatus


class AgentSessionSerializer(serializers.ModelSerializer):
    active_phases = serializers.SerializerMethodField()
    target_base_url = serializers.CharField(
        source="target.base_url", read_only=True,
    )
    target = serializers.PrimaryKeyRelatedField(
        queryset=ScanTarget.objects.all(),
    )
    mission_profile = serializers.CharField(
        default="juice_shop_scoreboard",
    )

    class Meta:
        model = AgentSession
        fields = (
            "id", "scan_run", "scan_target_run", "target",
            "status", "current_phase", "mission_profile",
            "autonomy_mode", "mission_budget", "consumed_budget",
            "progress_counters", "model_policy", "roe_snapshot",
            "started_at", "finished_at", "created_at", "updated_at",
            "active_phases", "target_base_url",
        )
        read_only_fields = (
            "id", "scan_run", "scan_target_run",
            "status", "current_phase",
            "autonomy_mode", "mission_budget", "consumed_budget",
            "progress_counters", "model_policy", "roe_snapshot",
            "started_at", "finished_at", "created_at", "updated_at",
            "active_phases", "target_base_url",
        )

    def get_active_phases(self, obj: AgentSession) -> list[str]:
        from .mission_profiles import get_profile
        try:
            profile = get_profile(obj.mission_profile)
            return profile.phases
        except KeyError:
            return [c.value for c in AgentPhase]

    def validate_mission_profile(self, value: str) -> str:
        from .mission_profiles import get_profile
        try:
            get_profile(value)
        except KeyError as exc:
            raise serializers.ValidationError(str(exc))
        return value

    def validate(self, attrs: dict) -> dict:
        target = attrs["target"]
        active = AgentSession.objects.filter(
            target=target,
            status__in=[
                SessionStatus.PENDING,
                SessionStatus.RUNNING,
                SessionStatus.PAUSED,
            ],
        ).exists()
        if active:
            raise serializers.ValidationError(
                {"target": "Target already has an active agent session."}
            )
        return attrs

    def create(self, validated_data: dict) -> AgentSession:
        from django.db import transaction

        from apps.scans.models import ScanRun, ScanTargetRun

        from .event_log import emit_session_started
        from .mission_profiles import get_profile
        from .persistence import create_session

        target = validated_data["target"]
        profile_name = validated_data["mission_profile"]
        profile = get_profile(profile_name)

        with transaction.atomic():
            target = ScanTarget.objects.select_for_update().get(pk=target.pk)
            active = AgentSession.objects.filter(
                target=target,
                status__in=[
                    SessionStatus.PENDING,
                    SessionStatus.RUNNING,
                    SessionStatus.PAUSED,
                ],
            ).exists()
            if active:
                raise serializers.ValidationError(
                    {"target": "Target already has an active agent session."}
                )
            scan_run = ScanRun.objects.create(
                project=target.project,
                stub_slug="agent.v3",
            )
            scan_run.start()
            target_run = ScanTargetRun.objects.create(
                scan_run=scan_run, target=target,
            )
            session = create_session(
                scan_run=scan_run,
                target_run=target_run,
                target=target,
                mission_profile=profile_name,
                model_policy=profile.model_policy,
                mission_budget=profile.mission_budget,
            )
            emit_session_started(session)

        return session
```
