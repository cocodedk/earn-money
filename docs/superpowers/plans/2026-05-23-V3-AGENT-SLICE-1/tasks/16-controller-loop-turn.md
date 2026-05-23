# Task 16 — Controller: _run_turn()

Part of [Task 16](16-controller-loop.md). Same file as
[16-controller-loop-impl.md](16-controller-loop-impl.md).

```python
# backend/apps/agent/controller.py (continued — same class)

    async def _run_turn(
        self, turn: Any, budget: BudgetTracker, plateau: PlateauDetector,
    ) -> str:
        system = build_system_prompt(
            objective=self._objective,
            phase=self._session.current_phase,
            allowed_actions=SLICE_1_ACTIONS,
            budget_remaining={"turns": budget.remaining("turns")},
        )
        if not self._messages:
            self._messages.append({
                "role": "user",
                "content": "Begin your mission. Propose your first action.",
            })

        resp = await self._provider.complete(system, self._messages)
        turn.prompt_hash = hashlib.sha256(system.encode()).hexdigest()[:16]
        turn.response_hash = hashlib.sha256(
            resp.raw_text.encode(),
        ).hexdigest()[:16]
        turn.input_tokens = resp.input_tokens
        turn.output_tokens = resp.output_tokens
        turn.prompt_artifact_ref = f"prompt_{turn.index}"
        turn.response_artifact_ref = f"response_{turn.index}"
        turn.status = TurnStatus.ACTION_PROPOSED
        turn.save(update_fields=[
            "prompt_hash", "response_hash", "input_tokens",
            "output_tokens", "prompt_artifact_ref",
            "response_artifact_ref", "status", "updated_at",
        ])

        try:
            raw = json.loads(resp.raw_text)
            envelope = parse_action(raw)
        except (json.JSONDecodeError, InvalidActionError) as e:
            action = record_action(
                turn=turn,
                action_type=(
                    raw.get("action", "unknown")
                    if isinstance(raw, dict) else "unknown"
                ),
                args_redacted={}, goal="",
                validation_status=ValidationStatus.INVALID_SCHEMA,
            )
            action.denial_reason = str(e)
            action.execution_status = ExecutionStatus.SKIPPED
            action.save(update_fields=[
                "denial_reason", "execution_status", "updated_at",
            ])
            finish_turn(turn, TurnStatus.ACTION_DENIED)
            emit_action_denied(self._session, turn.index, "unknown", str(e))
            plateau.record_invalid()
            self._messages.append({"role": "assistant", "content": resp.raw_text})
            self._messages.append({
                "role": "user",
                "content": format_observation_message(
                    None, denial_reason=str(e),
                ),
            })
            return "continue"

        try:
            check_phase_action(self._session.current_phase, envelope.action)
        except PhaseViolationError as e:
            action = record_action(
                turn=turn, action_type=envelope.action,
                args_redacted=raw.get("args", {}), goal=envelope.goal,
                validation_status=ValidationStatus.DENIED_PHASE,
            )
            action.denial_reason = str(e)
            action.execution_status = ExecutionStatus.SKIPPED
            action.save(update_fields=[
                "denial_reason", "execution_status", "updated_at",
            ])
            finish_turn(turn, TurnStatus.ACTION_DENIED)
            emit_action_denied(
                self._session, turn.index, envelope.action, str(e),
            )
            plateau.record_denial()
            self._messages.append({"role": "assistant", "content": resp.raw_text})
            self._messages.append({
                "role": "user",
                "content": format_observation_message(
                    None, denial_reason=str(e),
                ),
            })
            return "continue"

        action = record_action(
            turn=turn, action_type=envelope.action,
            args_redacted=raw.get("args", {}),
            goal=envelope.goal, reason=envelope.reason,
            hypothesis=envelope.hypothesis,
            validation_status=ValidationStatus.VALID,
        )

        obs_dict = await self._execute_action(envelope, action, turn)
        finish_turn(turn, TurnStatus.COMPLETED)
        emit_action_executed(self._session, turn.index, envelope.action)

        self._messages.append({"role": "assistant", "content": resp.raw_text})
        if obs_dict:
            self._messages.append({
                "role": "user",
                "content": format_observation_message(obs_dict),
            })
        plateau.record_turn(new_routes=0, new_elements=0)

        if envelope.action == "stop":
            return "stop"
        if envelope.action == "request_phase_transition":
            return "phase_transition"
        return "continue"
```

Continues in [16-controller-loop-execute.md](16-controller-loop-execute.md).
