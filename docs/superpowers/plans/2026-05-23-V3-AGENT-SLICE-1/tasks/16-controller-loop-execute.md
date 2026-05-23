# Task 16 — Controller: _execute_action()

Part of [Task 16](16-controller-loop.md). Same file as
[16-controller-loop-impl.md](16-controller-loop-impl.md).

```python
# backend/apps/agent/controller.py (continued — same class)

    async def _execute_action(
        self, envelope: Any, action: Any, turn: Any, budget: BudgetTracker,
    ) -> dict[str, Any] | None:
        from django.utils import timezone
        action.execution_status = ExecutionStatus.EXECUTED
        action.executed_at = timezone.now()
        action.save(update_fields=[
            "execution_status", "executed_at", "updated_at",
        ])

        if envelope.action == "observe_page":
            network = self._driver.drain_network_log()
            budget.consume("http_requests", len(network))
            obs = await self._obs_builder.build_page_observation(
                page=self._driver.page, turn=turn.index,
                phase=self._session.current_phase,
                action_ref=f"act_{turn.index}",
                network_entries=network,
            )
            obs_dict = obs.to_dict()
            record_observation(
                action=action, observation_type="page",
                data=obs_dict,
                content_hash=hashlib.sha256(
                    json.dumps(obs_dict).encode(),
                ).hexdigest()[:16],
            )
            return obs_dict

        if envelope.action == "navigate":
            budget.check("browser_actions")
            path = envelope.parsed.path
            if not path and envelope.parsed.url_ref:
                path = self._obs_builder.resolve_url_ref(
                    envelope.parsed.url_ref,
                )
            if not path:
                path = "/"
            await self._driver.navigate(path)
            budget.consume("browser_actions", 1)
            network = self._driver.drain_network_log()
            budget.consume("http_requests", len(network))
            obs = await self._obs_builder.build_page_observation(
                page=self._driver.page, turn=turn.index,
                phase=self._session.current_phase,
                action_ref=f"act_{turn.index}",
                network_entries=network,
            )
            obs_dict = obs.to_dict()
            record_observation(
                action=action, observation_type="page",
                data=obs_dict,
                content_hash=hashlib.sha256(
                    json.dumps(obs_dict).encode(),
                ).hexdigest()[:16],
            )
            return obs_dict

        if envelope.action == "inspect_asset":
            budget.check("asset_inspections")
            asset_path = self._obs_builder.resolve_asset_ref(envelope.parsed.asset_ref)
            if not asset_path:
                action.execution_status = ExecutionStatus.FAILED
                action.denial_reason = f"Unknown asset ref: {envelope.parsed.asset_ref}"
                action.save(update_fields=[
                    "execution_status", "denial_reason", "updated_at",
                ])
                return {"error": action.denial_reason}
            content, size, truncated = await self._driver.fetch_asset(asset_path)
            budget.consume("asset_inspections", 1)
            budget.consume("http_requests", 1)
            asset_obs = AssetObservation(
                asset_ref=envelope.parsed.asset_ref,
                path=asset_path,
                type="script", size_bytes=size, truncated=truncated,
                excerpts=[], strings_of_interest=[],
            )
            obs_dict = asset_obs.to_dict()
            record_observation(
                action=action, observation_type="asset",
                data=obs_dict,
                content_hash=hashlib.sha256(
                    content.encode(),
                ).hexdigest()[:16],
            )
            return obs_dict

        if envelope.action == "store_note":
            record_note(
                session=self._session, turn=turn,
                note_type=envelope.parsed.note_type,
                content=envelope.parsed.content,
            )
            emit_note_created(
                self._session, envelope.parsed.note_type, turn.index,
            )
            return None

        if envelope.action == "submit_candidate":
            record_note(
                session=self._session, turn=turn,
                note_type="candidate",
                content={
                    "category": envelope.parsed.category,
                    "description": envelope.parsed.description,
                },
                evidence_refs=envelope.parsed.evidence_refs,
            )
            emit_note_created(self._session, "candidate", turn.index)
            return None

        return None
```
